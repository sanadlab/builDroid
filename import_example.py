import buildAnaDroid
import os
from dotenv import load_dotenv

cwd = os.getcwd()
env_path = os.path.join(cwd, '.env')

# Check if the file exists and is a file before trying to load it.
if os.path.isfile(env_path):
    # Directly provide the confirmed path to load_dotenv.
    load_dotenv(dotenv_path=env_path)

source = "diskusage"
buildAnaDroid.process_repository(repo_source=source, keep_container=True, local_path=True)

if "API_KEY" in os.environ:
    del os.environ["API_KEY"]
if "BASE_URL" in os.environ:
    del os.environ["BASE_URL"]
if "LLM_MODEL" in os.environ:
    del os.environ["LLM_MODEL"]