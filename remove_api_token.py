import os
import re
from setup_api_key import replace_post_process, replace_openai_api_key

def restore_openai_base_url(file_path):
    """
    Resets the openai_api_base assignment in a config file to None, regardless of its previous value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = re.sub(
            r'openai_api_base: Optional\[str\] = .*',
            'openai_api_base: Optional[str] = None',
            content
        )

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to reset base_url in {file_path}: {e}")

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

def restore_other_llm_model(file_path):
    """
    Replaces the other_llm assignment in a Python config file regardless of the current value.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = re.sub(
            r'other_llm: str = ".*?"',
            f'other_llm: str = None',
            content
        )

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to update model in {file_path}: {e}")

def restore_placeholder(file_path, value, placeholder):
    """
    Replace all occurrences of a value in a file with the original placeholder.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        updated_content = content.replace(value, placeholder)

        with open(file_path, 'w') as file:
            file.write(updated_content)
    except Exception as e:
        print(f"Failed to restore placeholder in {file_path}: {e}")

def main():
    files = ["autogpt/.env", "run.sh"]

    token_path = "openai_token.txt"
    config_path = "autogpt/config/config.py"

    if not os.path.exists(token_path):
        print("Token file not found. Nothing to restore.")
        return

    try:
        with open(token_path, "r") as token_file:
            lines = [line.strip() for line in token_file.readlines()]
            if not lines:
                print("Token file is empty.")
                return
            api_key = lines[0]
    except Exception as e:
        print(f"Error reading {token_path}: {e}")
        return

    # Restore base_url to None
    restore_openai_base_url(config_path)
    restore_other_llm_model(config_path)
    replace_post_process("GLOBAL-API-KEY-PLACEHOLDER")

    # Restore API key placeholders
    for file_path in files:
        replace_openai_api_key(file_path)
    print("API Token reset complete.")

if __name__ == "__main__":
    main()
