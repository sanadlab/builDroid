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
    
        
def extract_agent_log(project_name):
    file_path = f"tests/{project_name}/logs/prompt_history"
    extracted_data = ""
    return extracted_data

def run_post_process(project_name):
    if os.path.exists("project_meta_data.json"):
        os.remove("project_meta_data.json")
    # Build paths
    success_file = f"tests/{project_name}/saved_contexts/SUCCESS"

    # Extract agent log
    try:
        extracted_content = extract_agent_log(project_name)
    except:
        return False
    
    if os.path.exists(success_file):
        return True
    
    return False

    # Summarize problems encountered
    while True:
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
        problems_memory = f"tests/{project_name}/output/FAILURE"
        with open(problems_memory, 'w') as f:
            f.write(response)
        break

    # Print FAILURE
    print("FAILURE")

if __name__ == "__main__":
    run_post_process()
