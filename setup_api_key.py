import os
import sys

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

        print(f"Updated {placeholder} in {file_path}")
    except Exception as e:
        print(f"Failed to update {file_path}: {e}")


def main():
    files_and_placeholders = [
        ("autogpt/.env", "GLOBAL-API-KEY-PLACEHOLDER"),
        ("run.sh", "GLOBAL-API-KEY-PLACEHOLDER"),
    ]
    if os.path.exists("openai_token.txt"):
        with open("openai_token.txt") as ott:
            replacement_value = ott.read()
        if replacement_value.startswith("sk-"):
            # Replace placeholders in files
            replace_placeholder("autogpt/config/config.py","openai_api_base: Optional[str] = \"https://api.together.xyz/v1\"","openai_api_base: Optional[str] = None")
            for file_path, placeholder in files_and_placeholders:
                replace_placeholder(file_path, placeholder, replacement_value)
            print("API key Setup complete.")
            return
        else:
            while True:
                cont = input("Provided key is not compatible with openAI. Continue? (yes/no): ").strip()
                if cont.startswith("y") or cont.startswith("Y"):
                    replace_placeholder("autogpt/config/config.py","openai_api_base: Optional[str] = None","openai_api_base: Optional[str] = \"https://api.together.xyz/v1\"")
                    for file_path, placeholder in files_and_placeholders:
                        replace_placeholder(file_path, placeholder, replacement_value)
                    print("API key Setup complete.")
                    return
                else:
                    print("Incompatible API key: Exiting program.")
                    sys.exit(1)
    else:
        print("API token file not detected. Please provide your OpenAI API-KEY.")
        replacement_value = input("OpenAI API-KEY: ").strip()
        if replacement_value.startswith("sk-"):
            replace_placeholder("autogpt/config/config.py","openai_api_base: Optional[str] = \"https://api.together.xyz/v1\"","openai_api_base: Optional[str] = None")
            for file_path, placeholder in files_and_placeholders:
                replace_placeholder(file_path, placeholder, replacement_value)
            # Save the replacement value to token.txt
            with open("openai_token.txt", "w") as token_file:
               token_file.write(replacement_value)
            print("API key Setup complete. API token file was created: openai_token.txt")
            return
        else:
            while True:
                cont = input("Provided key is not compatible with openAI. Continue? (yes/no): ").strip()
                if cont.startswith("y") or cont.startswith("Y"):
                    replace_placeholder("autogpt/config/config.py","openai_api_base: Optional[str] = None","openai_api_base: Optional[str] = \"https://api.together.xyz/v1\"")
                    for file_path, placeholder in files_and_placeholders:
                        replace_placeholder(file_path, placeholder, replacement_value)
                    with open("openai_token.txt", "w") as token_file:
                        token_file.write(replacement_value)
                    print("API key Setup complete. API token file was created: openai_token.txt")
                    return
                else:
                    print("Incompatible API key: Exiting program.")
                    sys.exit(1)

if __name__ == "__main__":
    main()