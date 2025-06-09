import os
import sys

def parse_token_file(file_path):
    """
    Reads openai_token.txt and extracts API key, base_url, and model.
    Returns a tuple: (api_key, base_url, llm_model)
    """
    try:
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f.readlines()]
            api_key = lines[0] if len(lines) >= 1 else None
            base_url = lines[1] if len(lines) >= 2 else None
            llm_model = lines[2] if len(lines) >= 3 else None
            return api_key, base_url, llm_model
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None, None
    
def api_token_setup():
    """
    Sets up api key, base url, and llm model as environment variables for buildAnaDroid.
    """
    if os.path.exists("openai_token.txt"):
        api_key, base_url, llm_model = parse_token_file("openai_token.txt")

        if not api_key:
            print("API key missing in openai_token.txt. Exiting.")
            sys.exit(1)
        
        os.environ["api_key"] = api_key
        if base_url is not None:
            os.environ["base_url"] = base_url
        if llm_model is not None:
            os.environ["llm_model"] = llm_model

        print("API token setup complete.")
        if base_url:
            print(f"Provider: {base_url}")
        else:
            print("Provider: OpenAI default (or not specified)")
        if llm_model:
            print(f"Model: {llm_model}")
        else:
            print("Model: Not specified")
    else:
        print("API token file not detected. Please create `openai_token.txt` with at least the API key.")
        sys.exit(1)

def api_token_reset():
    """
    Resets api key, base url, and llm model environment variables.
    """
    if os.environ.get("api_key"):
        del os.environ["api_key"]
    if os.environ.get("base_url"):
        del os.environ["base_url"]
    if os.environ.get("llm_model"):
        del os.environ["llm_model"]
