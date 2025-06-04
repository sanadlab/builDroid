import os
import re
import sys

import warnings
warnings.filterwarnings("ignore")

import openai
from google import genai

def ask_chatgpt(query, system_message):
    """
    Asks a question to either OpenAI's ChatGPT or Google's Gemini models.

    Args:
        query (str): The question to ask the model.
        system_message (str): The system message to guide the model's response.
        model (str, optional): The model to use.

    Returns:
        str: The content of the assistant's response.
    """
    # Set up the OpenAI API key
    api_key = os.environ.get("api_key")
    # Update base url for different API providers
    base_url = os.environ.get("base_url")
    llm_model = os.environ.get("llm_model")
    print("Post processing with model: ", llm_model)
    if "google" in base_url: # Gemini version
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=llm_model, contents=system_message + "\n" + query)  # Combine system and user messages
        return response.text
    
        
def extract_agent_log(log_file, output):
    with open(log_file, 'r', encoding='utf-8') as file:
        log_data = file.read()
    
    # Extract sections specific to ASSISTANT responses
    assistant_sections = re.findall(r'--------------- ASSISTANT ----------------\n(.*?)\n------------------ USER ------------------', log_data, re.DOTALL)
    
    thoughts_pattern = r'"thoughts": "(.*?)"'
    command_pattern = r'"command": ({.*?}\n})'
    user_response_pattern = r'The result of executing that last command is:\n(.*?)=========================================='
    
    thoughts, commands, user_responses = [], [], []
    
    for section in assistant_sections:
        thoughts.extend(re.findall(thoughts_pattern, section, re.DOTALL))
        commands.extend(re.findall(command_pattern, section, re.DOTALL))
    
    user_responses = re.findall(user_response_pattern, log_data, re.DOTALL)
    
    # Ensure all lists have the same length
    min_length = min(len(thoughts), len(commands), len(user_responses))
    thoughts, commands, user_responses = thoughts[:min_length], commands[:min_length], user_responses[:min_length]
        
    extracted_data = ""
    
    os.makedirs("problems_memory/extracted_logs/", exist_ok=True)
    with open(f"problems_memory/extracted_logs/{output}.txt", 'w') as txtfile:
        for i in range(min_length):
            if len(str(user_responses[i])) > 300:
                entry = f"Thoughts:{thoughts[i]}\nCommand:\n{commands[i]}\nOutput:\n{str(user_responses[i][:150])+str(user_responses[i][-150:])}\n==========================================\n"
            else:
                entry = f"Thoughts:{thoughts[i]}\nCommand:\n{commands[i]}\nOutput:\n{user_responses[i]}\n==========================================\n"
            txtfile.write(entry)
            extracted_data += entry

    return extracted_data

def main():
    if len(sys.argv) != 2:
        print("Usage: python post_process.py <project_name>")
        sys.exit(1)

    project_name = sys.argv[1]
    project_name = project_name.replace(".git","")

    # Read the last line of experiments_list.txt
    experiments_file = "experimental_setups/experiments_list.txt"
    if not os.path.exists(experiments_file):
        print(f"Error: {experiments_file} does not exist.")
        sys.exit(1)

    with open(experiments_file, 'r') as f:
        lines = f.readlines()
        if not lines:
            print(f"Error: {experiments_file} is empty.")
            sys.exit(1)
        last_line = lines[-1].strip()

    # Build paths
    success_file = f"experimental_setups/{last_line}/saved_contexts/{project_name}/SUCCESS"

    # Extract agent log
    try:
        extracted_content = extract_agent_log(f"experimental_setups/{last_line}/logs/prompt_history_{project_name}", f"extracted_log_{project_name}")
    except:
        print("FAILURE")
        return
    
    if os.path.exists(success_file):
        print("SUCCESS")
        return
    
    # Summarize problems encountered
    while True:
        try:
            # Prepare the query for ask_chatgpt
            query = (
                f"the following would represent the sequence of commands and reasoning made by an LLM trying to install \"{project_name}\" project from source code and execute test cases. "
                "I want you to summarize the encountered problems and give advice for next attempt. Be precise and concise. Address the most important and critical issues (ignore non critical warnings and so). Your response should have one header: ### Feedback from previous installation attempts\n"
                f"+ {extracted_content}"
            )
            
            system_message = (
                "You are a helpful software engineering assistant with capabilities of installing, building, configuring, and testing software projects."
            )

            # Call ask_chatgpt
            response = ask_chatgpt(query, system_message)

            # Save the response to problems_memory/{project_name}
            problems_memory = f"problems_memory/{project_name}"
            with open(problems_memory, 'w') as f:
                f.write(response)
            break
        except:
            print("ask_chatgpt failed. Retrying..")
            extracted_content = str(extracted_content[:-200])
            pass

    # Print FAILURE
    print("FAILURE")

if __name__ == "__main__":
    main()
