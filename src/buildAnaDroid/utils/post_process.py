import os
import re

import warnings
warnings.filterwarnings("ignore")

from openai import OpenAI
from google import genai
from buildAnaDroid.agents.base import create_chat_completion
from importlib.resources import files
import json

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
    if "google" in base_url: # Gemini version
        client = genai.Client(api_key=api_key)
    else:
        client = OpenAI(api_key=api_key)
    return create_chat_completion(client=client, model=llm_model, prompt=prompt)
    
        
def extract_agent_log(project_name):
    file_path = f"buildAnaDroid_tests/{project_name}/prompt_history"
    with open(file_path, "r", encoding="utf-8") as f:
        extracted_data = f.read()
    return extracted_data

class PatternClassifier:
    def __init__(self):
        # Define rules mapping specific issues to regex patterns
        # The order can matter if logs contain multiple errors.
        self.rules = {
            "Process Issue": {
                "MISSING_LOCAL_PROPERTIES": re.compile(r"SDK location not found"),
                "MISSING_KEYSTORE": re.compile(r"Keystore file '.*' not found for signing config"),
                "MISSING_GRADLE_WRAPPER": re.compile(r"Could not find or load main class org.gradle.wrapper.GradleWrapperMain"),
                "NON_DEFAULT_BUILD_COMMAND": re.compile(r"Task '.*' not found"),
            },
            "Environment Issue": {
                "GRADLE_VERSION": re.compile(r"Failed to notify project evaluation listener"),
                "JDK_VERSION": re.compile(r"Unsupported class file major version (\d+)"),
                "ANDROID_SDK_VERSION": re.compile(r"Failed to find Build Tools revision"),
                "REMOVED_DEPENDENCY": re.compile(r"Could not resolve all files for configuration"),
            },
            "Project Issue": {
                "CONFIG_VERSION_CONFLICT": re.compile(r"try editing the distributionUrl"),
                "COMPILATION_ERROR": re.compile(r"Compilation failed; see the compiler error output for details."),
            }
        }

    def classify(self, log_output: str) -> tuple[str, str] | None:
        """
        Classifies the error in a log using predefined regex rules.

        Returns:
            A tuple (category, specific_issue) if a match is found, otherwise None.
        """
        for category, issues in self.rules.items():
            for specific_issue, pattern in issues.items():
                if pattern.search(log_output):
                    return (category, specific_issue)
        return None
    
def extract_build_attempts(extracted_content: str) -> list[dict[str, str]]:
    """
    Extracts build attempts from the provided content.

    Args:
        extracted_content (str): The content containing build attempts.

    Returns:
        list[dict[str, str]]: A list of dictionaries with 'log' and 'timestamp' for each build attempt.
    """
    build_attempts = []
    # Split the content by lines
    lines = extracted_content.splitlines()
    current_attempt = ""
    log = False
    for line in lines:
        if "FAILURE: Build" in line:
            log = True
        if log:
            current_attempt += line + "\n"
        if "BUILD FAILED in" in line:
            log = False
            build_attempts.append(current_attempt.strip())
            current_attempt = ""

    return build_attempts

def run_post_process(project_name):
    # Extract agent log
    try:
        extracted_content = extract_agent_log(project_name)
    except:
        return False
    
    error_summary = {
            "Process Issue": {
                "MISSING_LOCAL_PROPERTIES": 0,
                "MISSING_KEYSTORE": 0,
                "MISSING_GRADLE_WRAPPER": 0,
                "NON_DEFAULT_BUILD_COMMAND": 0,
                "General": 0,  # General issues not classified
            },
            "Environment Issue": {
                "GRADLE_VERSION": 0,
                "JDK_VERSION": 0,
                "ANDROID_SDK_VERSION": 0,
                "REMOVED_DEPENDENCY": 0,
                "General": 0,  # General issues not classified
            },
            "Project Issue": {
                "CONFIG_VERSION_CONFLICT": 0,
                "COMPILATION_ERROR": 0,
                "General": 0,  # General issues not classified
            },
            "Unknown": 0
        }
    unique_errors_identified = set()
    classifier = PatternClassifier()
    
    build_attempts = extract_build_attempts(extracted_content)
    unclassified_logs = []
    for attempt in build_attempts:
        if "failed" in attempt:
            classification = classifier.classify(attempt)
            if classification:
                category, specific_issue = classification
                if specific_issue not in unique_errors_identified:
                    error_summary[category][specific_issue] += 1
                    unique_errors_identified.add(specific_issue)
            else:
                # This log contains a failure but couldn't be classified by rules
                unclassified_logs.append(attempt)

    # --- Step 2: LLM Fallback for Unclassified Errors ---
    if unclassified_logs:
        print(f"Found {len(unclassified_logs)} unclassified error(s). Falling back to LLM for summary.")
        # We only call the LLM if there's something it needs to do.
        # We pass only the unclassified logs to save tokens and focus the LLM.
        files_path = files("buildAnaDroid.prompts.prompt_files").joinpath("post_process_prompt")
        with files_path.open("r", encoding="utf-8") as prompt_file:
            prompt = prompt_file.read()
        prompt += str(unclassified_logs)
        response = ask_chatgpt(prompt)
        with open(f"buildAnaDroid_tests/{project_name}/output/unknown_error_llm_summary.txt", "w") as f:
            f.write(response)
        # Parse the LLM response
        try:
            llm_summary = json.loads(response)
        except json.JSONDecodeError:
            start_index = response.find('[')
            end_index = response.rfind(']')
            try:
                json_string = response[start_index:end_index + 1]
                llm_summary = json.loads(json_string)
            except json.JSONDecodeError:
                print("LLM response is not in JSON format. Please check the response.")
                llm_summary = []
        # Merge LLM results into our main summary
        for entry in llm_summary:
            if entry["taxonomy"] == "Unknown":
                error_summary["Unknown"] += 1
            else:
                error_summary[entry["taxonomy"]]["General"] += 1
    
    with open(f"buildAnaDroid_tests/{project_name}/output/error_summary.json", "w") as f:
        json.dump(error_summary, f, indent=4)

    if os.path.exists(f"buildAnaDroid_tests/{project_name}/saved_contexts/SUCCESS"):
        return True

    # Prepare the query for ask_chatgpt
    summarize_failure_prompt = (
        f"You are a helpful software engineering assistant with capabilities of installing, building, configuring, and testing software projects. The following would represent the sequence of commands and reasoning made by an LLM trying to install \"{project_name}\" project from source code and execute test cases. "
        "I want you to summarize the encountered problems and give advice for next attempt. Be precise and concise. Address the most important and critical issues (ignore non critical warnings and so).\n"
        f"\n\n==================Prompt History Start==================\n{extracted_content}\n==================Prompt History End=================="
        f"\n\n**IMPORTANT:** Ignore the JSON response format provided in Prompt History, which were used in other LLM requests.\nYour response should be in plain text and have one header: ### Feedback from previous installation attempts"
    )

    # Call ask_chatgpt
    print("Summarizing failure with LLM...")
    response = ask_chatgpt(summarize_failure_prompt)

    # Save the response to problems_memory/{project_name}"log"
    problems_memory = f"buildAnaDroid_tests/{project_name}/output/FAILURE"
    with open(problems_memory, 'w') as f:
        f.write(response)

    # Print FAILURE
    print("FAILURE")

if __name__ == "__main__":
    for project_name in os.listdir("buildAnaDroid_tests"):
        if project_name == "logs":
            continue
        run_post_process(project_name)
