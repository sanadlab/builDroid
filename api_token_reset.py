# unset_api_token.py
import sys

def main():
    variables_to_unset = [
        "api_key",
        "base_url",
        "llm_model"
    ]

    for var_name in variables_to_unset:
        print(f"unset {var_name}") # Command to stdout for shell to evaluate
    print("API token reset complete.", file=sys.stderr) # To stderr

if __name__ == "__main__":
    main()