import os
import re
import json
import sys
import pandas as pd
import argparse

import warnings
warnings.filterwarnings("ignore")

import openai

def ask_chatgpt(query, system_message, model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"):
    # Read the OpenAI API token from a file
    with open("openai_token.txt") as opt:
        token = opt.read().strip()

    # Set up the OpenAI API key
    openai.api_key = token
    # Update base url for different API providers
    if not token.startswith("sk-"):
        openai.api_base = "https://api.together.xyz/v1"

    # Construct the messages for the Chat Completion API
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": query}
    ]

    # Call the OpenAI API for chat completion
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages
    )

    # Extract and return the content of the assistant's response
    return response["choices"][0]["message"]["content"]

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

    with open(f"problems_memory/{output}.txt", 'w') as txtfile:
        for i in range(min_length):
            if len(str(user_responses[i])) > 200:
                entry = f"Thoughts:{thoughts[i]}\nCommand:\n{commands[i]}\nOutput:\n{str(user_responses[i][:150])+str(user_responses[i][-50:])}\n==========================================\n"
            else:
                entry = f"Thoughts:{thoughts[i]}\nCommand:\n{commands[i]}\nOutput:\n{user_responses[i]}\n==========================================\n"
            txtfile.write(entry)
            extracted_data += entry

    # Create DataFrame
    df = pd.DataFrame({
        "Thoughts": thoughts,
        "Command": commands,
        "Output": user_responses
    })
    
    # Save to Excel
    #df.to_excel(f"{output}.xlsx")
    
    #print(f"Extraction complete. Data saved to {output}.xslx")

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
    
    if os.path.exists(success_file):
        print("SUCCESS")
        return

    # Extract agent log
    extracted_content = extract_agent_log(f"experimental_setups/{last_line}/logs/prompt_history_{project_name}", f"extracted_log_{project_name}")
    '''
    # Find the cycle_XX file with the highest XX
    contexts_dir = f"experimental_setups/{last_line}/saved_contexts/{project_name}"
    if not os.path.exists(contexts_dir):
        print(f"Error: {contexts_dir} does not exist.")
        sys.exit(1)

    cycle_files = [f for f in os.listdir(contexts_dir) if f.startswith("cycle_") and f[6:].isdigit()]
    if not cycle_files:
        print(f"Error: No cycle files found in {contexts_dir}.")
        sys.exit(1)

    latest_cycle_file = max(cycle_files, key=lambda x: int(x[6:]))
    latest_cycle_path = os.path.join(contexts_dir, latest_cycle_file)

    # Read the JSON content of the latest cycle file
    with open(latest_cycle_path, 'r') as f:
        try:
            file_content = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from {latest_cycle_path}.")
            sys.exit(1)

    # Extract the desired content
    try:
        extracted_content = file_content["steps_object"]["1"]["result_of_step"]
    except KeyError as e:
        print(f"Error: Missing key in JSON structure: {e}")
        sys.exit(1)
    '''
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
            extracted_content = str(extracted_content[:-200])
            pass

    # Print FAILURE
    print("FAILURE")

if __name__ == "__main__":
    main()
