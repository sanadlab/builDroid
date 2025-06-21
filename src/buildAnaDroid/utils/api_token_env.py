import os
import sys

from dotenv import load_dotenv, find_dotenv

def api_token_setup():
    """
    Sets up API key, base URL, and LLM model as environment variables for buildAnaDroid
    by loading from a .env file.
    """
    env_path = find_dotenv()
    if not env_path:
        print("Warning: .env file not found.", file=sys.stderr)
    else:
        print(f"Loading environment variables from: {env_path}")
        load_dotenv(dotenv_path=env_path)

    if not os.getenv("API_KEY"):
        print("Error: API_KEY not found in .env file or environment variables.", file=sys.stderr)
        print("Please create a .env file in the project root with at least API_KEY=<your_key_here>.", file=sys.stderr)
        sys.exit(1)

    print("LLM configuration loaded successfully.")

    base_url_env = os.getenv("BASE_URL")
    llm_model_env = os.getenv("LLM_MODEL")

    if base_url_env:
        print(f"Provider: {base_url_env}")
    else:
        print("Provider: OpenAI default")

    if llm_model_env:
        print(f"Model: {llm_model_env}")
    else:
        if not base_url_env:
            llm_model = "gpt-4.1-mini"
        elif "google" in base_url_env:
            llm_model = "gemini-2.0-flash-lite"
        else:
            llm_model = "gpt-4.1-mini"
        os.environ["LLM_MODEL"] = llm_model
        print(f"Model: Not specified, default: {llm_model}")

def api_token_reset():
    """
    Resets api key, base url, and llm model environment variables.
    """
    if "API_KEY" in os.environ:
        del os.environ["API_KEY"]
    if "BASE_URL" in os.environ:
        del os.environ["BASE_URL"]
    if "LLM_MODEL" in os.environ:
        del os.environ["LLM_MODEL"]