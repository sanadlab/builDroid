import builDroid
import os

import debugpy
debugpy.listen(("0.0.0.0", 5678))

print("Waiting for debugger to attach...")
debugpy.wait_for_client()
print("Debugger attached!")

source = "weather-overview"
project_name = "jk7404_weather-overview"
apk_name = builDroid.process_repository(repo_source=source, override_project=True, local_path=True, project_name=project_name)
print("apk_name: " + apk_name)
print("apk_path: " + f"builDroid_tests/{project_name}/output/{apk_name}")