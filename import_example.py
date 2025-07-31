import builDroid
import os

cwd = os.getcwd()
env_path = os.path.join(cwd, '.env')

builDroid.utils.api_token_setup()

source = "diskusage"
builDroid.process_repository(repo_source=source, override_project=True, local_path=True, project_name="jk7404_diskusage")

builDroid.utils.api_token_reset()