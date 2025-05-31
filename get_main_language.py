import requests

def get_repo_languages(owner, repo):
    # GitHub API URL for languages of a repository
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"

    try:
        # Send a GET request to the GitHub API
        response = requests.get(url)

        # Check for successful response
        if response.status_code == 200:
            languages = response.json()
            if languages:
                # Sort languages by byte size (largest first) and get the primary language
                primary_language = max(languages, key=languages.get)
                print(f"{primary_language}")
                #print("All languages with byte usage:")
                #for lang, bytes_used in languages.items():
                #    print(f"- {lang}: {bytes_used} bytes")
            else:
                print("No languages detected for this repository.")
        else:
            print(f"Failed to fetch languages: {response.status_code} {response.reason}")
    except requests.RequestException as e:
        print(f"Error during request: {e}")

# Example usage
# Replace 'owner' and 'repo' with the repository's owner and name
owner = "pytest-dev"
repo = "pytest"
get_repo_languages(owner, repo)