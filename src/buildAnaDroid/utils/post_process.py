import os

import warnings
warnings.filterwarnings("ignore")

from openai import OpenAI
from google import genai
from ..agents.base import create_chat_completion

def ask_chatgpt(prompt):
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
    api_key = os.getenv("API_KEY", default="")
    # Update base url for different API providers
    base_url = os.getenv("BASE_URL", default="")
    llm_model = os.getenv("LLM_MODEL", default="")
    print("Post processing with model: ", llm_model)
    if "google" in base_url: # Gemini version
        client = genai.Client(api_key=api_key)
    else:
        client = OpenAI(api_key=api_key)
    return create_chat_completion(client=client, model=llm_model, prompt=prompt)
    
        
def extract_agent_log(project_name):
    file_path = f"tests/{project_name}/logs/prompt_history"
    with open(file_path, "r", encoding="utf-8") as f:
        extracted_data = f.read()
    return extracted_data

def run_post_process(project_name):
    # Build paths
    success_file = f"tests/{project_name}/saved_contexts/SUCCESS"

    # Extract agent log
    try:
        extracted_content = extract_agent_log(project_name)
    except:
        return False
    
    if os.path.exists(success_file):
        return True

    # Summarize problems encountered
    while True:
        # Prepare the query for ask_chatgpt
        prompt = (
            f"You are a helpful software engineering assistant with capabilities of installing, building, configuring, and testing software projects. The following would represent the sequence of commands and reasoning made by an LLM trying to install \"{project_name}\" project from source code and execute test cases. "
            "I want you to summarize the encountered problems and give advice for next attempt. Be precise and concise. Address the most important and critical issues (ignore non critical warnings and so).\n"
            f"\n\n==================Prompt History Start==================\n{extracted_content}\n==================Prompt History End=================="
            f"\n\n**IMPORTANT:** Ignore the JSON response format provided in Prompt History, which were used in other LLM requests.\nYour response should be in plain text and have one header: ### Feedback from previous installation attempts"
        )

        # Call ask_chatgpt
        response = ask_chatgpt(prompt)

        # Save the response to problems_memory/{project_name}
        problems_memory = f"tests/{project_name}/output/FAILURE"
        with open(problems_memory, 'w') as f:
            f.write(response)
        break

    # Print FAILURE
    print("FAILURE")

if __name__ == "__main__":
    run_post_process()
