import os
import sys

def parse_token_file(file_path):
    """
    Reads openai_token.txt and extracts API key, base_url, and model.
    Returns a tuple: (api_key, base_url, model_name)
    """
    try:
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f.readlines()]
            api_key = lines[0] if len(lines) >= 1 else None
            base_url = lines[1] if len(lines) >= 2 else None
            llm_model = lines[2] if len(lines) >= 3 else None
            return api_key, base_url, llm_model
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr) # To stderr
        return None, None, None

def shell_quote(s):
    """Properly quotes a string for shell export, handling single quotes within the string."""
    if s is None:
        return "''" # Represent None as an empty string in the shell
    # Replace ' with '\''
    return "'" + str(s).replace("'", "'\\''") + "'"

def main():
    if os.path.exists("openai_token.txt"):
        api_key, base_url, llm_model = parse_token_file("openai_token.txt")

        if not api_key:
            print("API key missing in openai_token.txt. Exiting.", file=sys.stderr) # To stderr
            sys.exit(1)

        # Print shell commands to stdout
        print(f"export api_key={shell_quote(api_key)}")
        # Only export if they exist, otherwise export an empty string or don't export
        if base_url is not None:
            print(f"export base_url={shell_quote(base_url)}")
        else:
            print(f"export base_url=''") # Or unset it: unset base_url
        if llm_model is not None:
            print(f"export llm_model={shell_quote(llm_model)}")
        else:
            print(f"export llm_model=''") # Or unset it: unset llm_model


        print("API token setup complete.", file=sys.stderr) # To stderr
        if base_url:
            print(f"Provider: {base_url}", file=sys.stderr)
        else:
            print("Provider: OpenAI default (or not specified)", file=sys.stderr)
        if llm_model:
            print(f"Model: {llm_model}", file=sys.stderr)
        else:
            print("Model: Not specified", file=sys.stderr)

    else:
        print("API token file not detected. Please create `openai_token.txt` with at least the API key.", file=sys.stderr) # To stderr
        sys.exit(1)

if __name__ == "__main__":
    main()