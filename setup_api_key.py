import os
import sys
import re

def replace_openai_api_key(file_path, new_key=None):
    """
    Replaces the openai_api_base assignment in a Python config file regardless of current value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = re.sub(
            r'OPENAI_API_KEY=.*',
            f'OPENAI_API_KEY="{new_key}"' if new_key else 'OPENAI_API_KEY=GLOBAL-API-KEY-PLACEHOLDER',
            content
        )

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to update api_key in {file_path}: {e}")

def replace_openai_base_url(file_path, new_base_url):
    """
    Replaces the openai_api_base assignment in a Python config file regardless of current value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = re.sub(
            r'openai_api_base: Optional\[str\] = .*',
            f'openai_api_base: Optional[str] = "{new_base_url}"' if new_base_url else 'openai_api_base: Optional[str] = None',
            content
        )

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to update base_url in {file_path}: {e}")

def replace_other_llm_model(file_path, new_model):
    """
    Replaces the other_llm assignment in a Python config file regardless of the current value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = re.sub(
            r'other_llm: str = .*',
            f'other_llm: str = "{new_model}"' if new_model else 'other_llm: str = None',
            content
        )

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to update model in {file_path}: {e}")

def replace_post_process(new_key, new_base_url=None, new_model=None):
    """
    Replaces the other_llm assignment in a Python config file regardless of the current value.
    """
    try:
        with open("post_process.py", 'r') as file:
            content = file.read()
        
        new_content = re.sub(
            r'openai.api_key = .*',
            f'openai.api_key = "{new_key}"' if new_key else 'openai.api_key = None',
            content
        )
        updated_content = re.sub(
            r'model=.*\)',
            f'model="{new_model}")' if new_model else 'model=None)',
            new_content
        )
        new_updated_content = re.sub(
            r'openai.api_base = .*',
            f'openai.api_base = "{new_base_url}"' if new_base_url else 'openai.api_base = None',
            updated_content
        )

        with open("post_process.py", 'w') as file:
            file.write(new_updated_content)
    except Exception as e:
        print(f"Failed to update post_process.py: {e}")

def replace_placeholder(file_path, placeholder, new_value):
    """
    Replace all occurrences of a placeholder in a file with a new value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = content.replace(placeholder, new_value)

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to update {file_path}: {e}")

def replace_openai_api_base_line(file_path, new_base_url):
    """
    Replace any line assigning to openai.api_base with a new URL, or set it to None if not provided.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        updated_content = re.sub(
            r'openai\.api_base\s*=\s*["\'].*?["\']',
            f'openai.api_base = "{new_base_url}"' if new_base_url else 'openai.api_base = None',
            content
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
    except Exception as e:
        print(f"Failed to update openai.api_base in {file_path}: {e}")

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
            model_name = lines[2] if len(lines) >= 3 else None
            return api_key, base_url, model_name
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None, None
    
def main():
    files = ["autogpt/.env", "run.sh"]
    config_path = "autogpt/config/config.py"

    if os.path.exists("openai_token.txt"):
        api_key, base_url, model_name = parse_token_file("openai_token.txt")

        if not api_key:
            print("API key missing in openai_token.txt. Exiting.")
            sys.exit(1)

        # Determine base_url config line replacement
        replace_openai_base_url(config_path, base_url)

        if model_name:
            replace_other_llm_model(config_path, model_name)
        replace_post_process(api_key, base_url, model_name)
        for file_path in files:
            replace_openai_api_key(file_path, api_key)

        print("API key setup complete.")
        print(f"Provider: {base_url if base_url else 'OpenAI default'}")
        print(f"Model: {model_name if model_name else 'Not specified'}")
        return

    else:
        print("API token file not detected. Please create `openai_token.txt` with at least the API key.")
        sys.exit(1)

if __name__ == "__main__":
    main()