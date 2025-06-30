"""Commands to call error solving functions"""

COMMAND_CATEGORY = "gradle_build_error_solver"
COMMAND_CATEGORY_TITLE = "Gradle Build Error Solver"

import os
import re
import shutil
from enum import Enum
from importlib.resources import files, as_file
import subprocess
from sys import version

from buildAnaDroid.commands.docker_helpers_static import execute_command_in_container
from buildAnaDroid.agents.agent import Agent
from buildAnaDroid.models.command_decorator import command

RES_DIR = "buildAnaDroid.files"
GRADLE_RES_DIR = os.path.join(RES_DIR, "build", "gradle")
GRADLE_WRAPPER_DIR = os.path.join(GRADLE_RES_DIR, "wrapper", "gradle")

@command(
    "fix_wrapper_mismatch",
    "error string: 'Failed to notify project evaluation listener'\nUpdates Gradle Wrapper version to be compatible with the Android Gradle Plugin version.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android Gradle Plugin to use",
            "required": True,
        }
    },
)
def fix_wrapper_mismatch(version: str, agent: Agent):
    print("Attempting to fix WRAPPER_MISMATCH_ERROR...")
    # 1. Find all build.gradle files
    find_cmd = f"find . -name 'build.gradle'"
    build_files_out = execute_command_in_container(agent.shell_socket, find_cmd)
    if 'build.gradle' not in build_files_out:
        return "Error: Could not find build.gradle files."

    for build_file in build_files_out.strip().split('\n'):
        if not build_file: continue
        # 2. Extract AGP version
        # Using sed to extract the version string: com.android.tools.build:gradle:VERSION
        # This regex captures what's between the last colon and the closing quote.
        extract_cmd = f"sed -n \"s/.*com\\.android\\.tools\\.build:gradle:\\([^']\\+\\).*/\\1/p\" {build_file}"
        agp_ver_out = execute_command_in_container(agent.shell_socket, extract_cmd)
        agp_version = agp_ver_out.strip()

        if agp_version:
            # 3. Determine and apply adequate Gradle version
            adequate_gradle_v = get_adequate_gradle_version(agp_version)
            print(f"Found AGP {agp_version}, requires Gradle ~{adequate_gradle_v}. Updating wrapper.")
            
            # Find the properties file and update it using sed
            prop_file_find_cmd = f"find . -name 'gradle-wrapper.properties'"
            prop_files_out = execute_command_in_container(agent.shell_socket, prop_file_find_cmd)

            for prop_file in prop_files_out.strip().split('\n'):
                 if not prop_file: continue
                 # This sed command replaces the version part of the distributionUrl
                 update_cmd = f"sed -i -E 's/(distributionUrl=.*gradle-)[^/]+(\\-all.zip)/\\1{adequate_gradle_v}\\2/' {prop_file}"
                 execute_command_in_container(agent.shell_socket, update_cmd)
            break # Assume the first build.gradle with a version is the root one

    return f"Gradle Wrapper updated to {adequate_gradle_v} based on AGP version {agp_version}."

@command(
    "fix_no_wrapper",
    "error string: 'Could not find or load main class org.gradle.wrapper.GradleWrapperMain'\nCopies the entire gradle wrapper template directory into the project.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android Gradle to use",
            "required": True,
        }
    },
)
def fix_no_wrapper(version: str, agent: Agent):
    print("Attempting to fix NO_WRAPPER error...")
    # Ensure the 'gradle' directory exists
    mkdir_cmd = f"mkdir -p gradle/wrapper"
    execute_command_in_container(agent.shell_socket, mkdir_cmd)
    # Copy the wrapper contents from resources
    if "gradle-wrapper.jar" not in execute_command_in_container(agent.shell_socket, f"find . -name \"gradle-wrapper.jar\""):
        with as_file(files("buildAnaDroid.files").joinpath("gradle-wrapper.jar")) as host_path_to_wrapper_jar:
            # Copy the gradle wrapper jar file
            try:
                subprocess.run(['docker', 'cp', str(host_path_to_wrapper_jar), f'{agent.container.id}:{agent.project_path}/gradle/wrapper/gradle-wrapper.jar'], check=True)
            except subprocess.CalledProcessError as e:
                return (f"Error copying gradle-wrapper.jar: {e}")
    if "gradle-wrapper.properties" not in execute_command_in_container(agent.shell_socket, f"find . -name \"gradle-wrapper.properties\""):
        with as_file(files("buildAnaDroid.files").joinpath("gradle-wrapper.properties")) as host_path_to_wrapper_properties:
            # Copy the gradle wrapper properties file
            try:
                subprocess.run(['docker', 'cp', str(host_path_to_wrapper_properties), f'{agent.container.id}:{agent.project_path}/gradle/wrapper/gradle-wrapper.properties'], check=True)
            except subprocess.CalledProcessError as e:
                return (f"Error copying gradle-wrapper.properties: {e}")
    return "Successfully copied gradle wrapper files to the project root."

@command(
    "fix_no_gradlew_exec",
    "error string: 'gradlew: No such file or directory'\nCopies the `gradlew` executable script to the project root and makes it executable.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android Gradle Plugin to use",
            "required": True,
        }
    },
)
def fix_no_gradlew_exec(version: str, agent: Agent):
    print("Attempting to fix NO_GRADLEW_EXEC error...")
    with as_file(files("buildAnaDroid.files").joinpath("gradlew")) as gradlew_path:
        try:
            subprocess.run(['docker', 'cp', str(gradlew_path), f'{agent.container.id}:{agent.project_path}/gradlew'], check=True)
        except subprocess.CalledProcessError as e:
            return f"Error copying gradlew: {e}"
    chmod_cmd = f"chmod +x gradlew"
    output = execute_command_in_container(agent.shell_socket, chmod_cmd)
    if output == "":
        return "Successfully copied and made gradlew executable."
    return f"Failed to make gradlew executable: {output}"

@command(
    "fix_no_target_platform",
    "error string: 'failed to find target with hash string android-([0-9]+)'\nDownloads the missing Android SDK platform.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android SDK platform to use",
            "required": True,
        }
    },
)
def fix_no_target_platform(version: str, agent: Agent):
    print(f"Required platform version: {version}. Attempting download.")
    # The 'yes' command automatically accepts licenses
    download_cmd = f"yes | sdkmanager \"platforms;android-{version}\""
    return execute_command_in_container(agent.shell_socket, download_cmd)

@command(
    "fix_no_build_tools",
    "error string: 'failed to find Build Tools revision'\nDownloads the missing Android Build Tools.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android SDK Build Tools to use",
            "required": True,
        }
    },
)
def fix_no_build_tools(version: str, agent: Agent):
    print("Attempting to fix NO_BUILD_TOOLS error...")
    print(f"Required build-tools version: {version}. Attempting download.")
    download_cmd = f"yes | sdkmanager \"build-tools;{version}\""
    return execute_command_in_container(agent.shell_socket, download_cmd)

@command(
    "fix_google_repo_error",
    "error string: 'method google() for arguments'\nUpgrades AGP to a version that supports the `google()` repository shortcut.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def fix_google_repo_error(command: str, agent: Agent):
    print("Attempting to fix GOOGLE_REPO_ERROR...")
    # Find root build file
    root_build_file = "build.gradle"
    min_agp_version = "3.6.3" # A safe version that supports google()
    
    # Replace the AGP version using sed
    update_cmd = (
        f"sed -i -E \"s/(com.android.tools.build:gradle:)[^']+/\\1'{min_agp_version}'/\" "
        f"{root_build_file}"
    )
    execute_command_in_container(agent.shell_socket, update_cmd)

    # Now, this will likely cause a wrapper mismatch, so we fix that pre-emptively.
    if "Gradle Wrapper updated" not in fix_wrapper_mismatch(min_agp_version, agent):
        return "Upgraded AGP version, but failed to update Gradle Wrapper. Please check manually."

    return f"Upgraded AGP version in {root_build_file} to {min_agp_version}."

@command(
    "fix_maybe_missing_google_repo",
    "error string: 'Could not resolve all dependencies for configuration'\nAdds the Google maven repository to the project.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def fix_maybe_missing_google_repo(command: str, agent: Agent):
    print("Attempting to fix MAYBE_MISSING_GOOGLE_REPO...")
    root_build_file = "build.gradle"

    # Add to allprojects block. A bit naive, but often works.
    allprojects_repo = "\\nallprojects { repositories { google() } }"
    add_allprojects_cmd = f"echo -e '{allprojects_repo}' >> {root_build_file}"
    execute_command_in_container(agent.shell_socket, add_allprojects_cmd)

    # Check if google() exists in buildscript.repositories
    # `grep -q` is silent and returns 0 if found, 1 if not.
    check_cmd = f"grep -q 'google()' {root_build_file}"
    if execute_command_in_container(agent.shell_socket, check_cmd) != "":
        # Not found, add it.
        buildscript_repo = "\\nbuildscript { repositories { google() } }"
        add_buildscript_cmd = f"echo -e '{buildscript_repo}' >> {root_build_file}"
        execute_command_in_container(agent.shell_socket, add_buildscript_cmd)
        return "Added google() repository to buildscript."
    else:
        return "google() repository already present in buildscript."

@command(
    "fix_ndk_bad_config",
    "error string: 'did not contain a valid NDK and couldn't be used'\nGenerates a local.properties file with correct SDK and NDK paths from within the container.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def fix_ndk_bad_config(command: str, agent: Agent):
    print("Attempting to fix NDK_BAD_CONFIG by dynamically generating local.properties...")

    # 1. Command to find the SDK path.
    # It checks standard environment variables first, then falls back to common locations.
    find_sdk_cmd = (
        "sh -c '"
        "if [ -n \"$ANDROID_SDK_ROOT\" ]; then echo \"$ANDROID_SDK_ROOT\"; "
        "elif [ -n \"$ANDROID_HOME\" ]; then echo \"$ANDROID_HOME\"; "
        "elif [ -d \"/opt/android-sdk\" ]; then echo \"/opt/android-sdk\"; "
        "elif [ -d \"/usr/lib/android-sdk\" ]; then echo \"/usr/lib/android-sdk\"; "
        "else echo \"SDK_NOT_FOUND\"; fi"
        "'"
    )
    sdk_path_out = execute_command_in_container(agent.shell_socket, find_sdk_cmd)
    sdk_path = sdk_path_out.strip()

    if sdk_path == "SDK_NOT_FOUND" or not sdk_path:
        return f"Error: Could not determine Android SDK path inside the container."
        
    print(f"Discovered SDK path: {sdk_path}")

    # 2. Command to find the latest NDK version directory within the SDK path.
    # `ls -1` lists one file per line. `2>/dev/null` suppresses errors if 'ndk' dir doesn't exist.
    # `tail -n 1` gets the last entry, which is often the latest version.
    find_ndk_cmd = f"sh -c 'ls -1 {sdk_path}/ndk 2>/dev/null | tail -n 1'"
    ndk_version_dir_out = execute_command_in_container(agent.shell_socket, find_ndk_cmd)
    ndk_version_dir = ndk_version_dir_out.strip()

    # 3. Construct the properties file content
    # Use double newlines for clarity in the echo command.
    properties_content = f"sdk.dir={sdk_path}\\n" \
                         f"sdk-location={sdk_path}\\n"

    if ndk_version_dir:
        ndk_path = f"{sdk_path}/ndk/{ndk_version_dir}"
        print(f"Discovered NDK path: {ndk_path}")
        properties_content += f"ndk.dir={ndk_path}\\n" \
                              f"ndk-location={ndk_path}\\n"
    else:
        print("Warning: NDK not found within SDK path. local.properties will not contain NDK paths.")

    # 4. Write the content to the local.properties file in the project root.
    # The `echo -e` command interprets the \n characters as newlines.
    write_cmd = f"echo -e '{properties_content}' > local.properties"
    execute_command_in_container(agent.shell_socket, write_cmd)

    return "Successfully generated and wrote local.properties."

@command(
    "fix_build_tools_cpu_error",
    "error string: 'Bad CPU type in executable'\nUpgrades the project's Build Tools to a newer version to resolve CPU architecture issues.",
    {
        "version": {
            "type": "string",
            "description": "The version of the build tools to upgrade to",
            "required": True,
        }
    },
)
def fix_build_tools_cpu_error(version: str, agent: Agent):
    print("Attempting to fix BUILD_TOOLS_CPU_ERROR...")
    # 1. Download the new version
    download_cmd = f"yes | sdkmanager \"build-tools;{version}\""
    execute_command_in_container(agent.shell_socket, download_cmd)

    # 2. Find all build.gradle files and replace the version string
    find_cmd = "find . -name 'build.gradle'"
    build_files_out = execute_command_in_container(agent.shell_socket, find_cmd)

    for bld_file in build_files_out.strip().split('\n'):
        if not bld_file: continue
        print(f"Updating buildToolsVersion in {bld_file}...")
        # This sed command finds `buildToolsVersion "x.y.z"` and replaces x.y.z
        replace_cmd = (
            f"sed -i -E \"s/(buildToolsVersion[[:space:]]*=?[[:space:]]*[\"'])[0-9.]+([\"'])/\\1{version}\\2/\" "
            f"'{bld_file}'"
        )
        execute_command_in_container(agent.shell_socket, replace_cmd)

    return f"Build Tools upgraded to {version} and updated in all build.gradle files."

@command(
    "fix_wrapper_error",
    "error string: 'try editing the distributionUrl'\nUpdates the Gradle Wrapper version based on an explicit recommendation in the error log.",
    {
        "error_msg": {
            "type": "string",
            "description": "The error message snippet from the Gradle build: 'Minimum supported Gradle version is (.*?)\. Current version'",
            "required": True,
        }
    },
)
def fix_wrapper_error(error_msg: str, agent: Agent):
    print("Attempting to fix WRAPPER_ERROR...")
    new_v = None

    # 1. Try to parse the recommended version from the error message
    match = re.search(r"Minimum supported Gradle version is (.*?)\. Current version", error_msg)
    if match:
        recom_v_str = match.groups()[0].strip()
        new_v = f"{recom_v_str}-all"
        print(f"Found recommended Gradle version in error log: {recom_v_str}")
    else:
        # 2. Fallback: derive from AGP version (logic from _fix_wrapper_mismatch)
        print("No recommendation found. Deriving Gradle version from AGP version.")
        root_build_file = "build.gradle"
        extract_cmd = f"sed -n \"s/.*com\\.android\\.tools\\.build:gradle:\\([^']\\+\\).*/\\1/p\" {root_build_file}"
        agp_ver_out = execute_command_in_container(agent.shell_socket, extract_cmd)
        agp_version = agp_ver_out.strip().split("\r\n\r")[1]
        
        if agp_version:
            new_v = get_adequate_gradle_version(agp_version)
            print(f"Found AGP {agp_version}, requires Gradle ~{new_v}.")

    if not new_v:
        return "Error: Could not determine a new Gradle version to use."

    prop_file = "gradle/wrapper/gradle-wrapper.properties"

    if prop_file:
        print(f"Updating Gradle version in {prop_file} to {new_v}...")
        update_cmd = f"sed -i -E 's/(distributionUrl=.*gradle-)[^/]+(\\-all.zip)/\\1{new_v}\\2/' {prop_file}"
        execute_command_in_container(agent.shell_socket, update_cmd)
    else:
        return "Error: Could not find gradle-wrapper.properties to update."
    return f"Gradle Wrapper updated to {new_v} based on the error log or AGP version."
        
def get_adequate_gradle_version(plugin_version):
    """
    Given the gradle plugin version, returns an adequate gradle version to match.
    This version is self-contained and does not require the DefaultSemanticVersion class.

    Based on https://developer.android.com/studio/releases/gradle-plugin#updating-gradle table.
    
    Args:
        plugin_version (str): The Android Gradle-plugin version string.

    Returns:
        str: The adequate Gradle version string (e.g., "6.7.1-all").
    """

    def parse_version_to_tuple(version_string):
        """
        A simple, robust parser that converts a version string into a comparable tuple.
        Example: "3.5.0-rc1" -> (3, 5, 0)
        """
        try:
            # 1. Clean the string: remove quotes and pre-release tags (e.g., -alpha, -rc1)
            cleaned_version = re.sub(r'["\']', '', str(version_string).strip())
            if "-" in cleaned_version:
                cleaned_version = cleaned_version.split("-")[0]
            
            # 2. Split into parts and ensure we have 3 components (major, minor, patch)
            parts = cleaned_version.split('.')
            parts = parts + ['0'] * (3 - len(parts)) # Pad with '0' if patch or minor are missing
            
            # 3. Convert to a tuple of integers
            return tuple(map(int, parts[:3]))
        except (ValueError, IndexError):
            # If parsing fails for any reason, return a base version to avoid crashes
            return (0, 0, 0)

    # Parse the input plugin version into a comparable tuple
    v = parse_version_to_tuple(plugin_version)

    # Compare the tuple against predefined version ranges
    if (1, 0, 0) <= v <= (1, 1, 3):
        return "2.3-all"
    elif (1, 2, 0) <= v <= (1, 3, 1):
        return "2.9-all"
    elif v == (1, 5, 0):
        return "2.13-all"
    elif (2, 0, 0) <= v <= (2, 1, 2):
        return "2.13-all"
    elif (2, 1, 3) <= v <= (2, 2, 3):
        return "3.5-all"
    elif (2, 3, 0) <= v < (3, 0, 0): # Using '<' for exclusive upper bound
        return "3.3-all"
    elif (3, 0, 0) <= v < (3, 1, 0):
        return "4.1-all"
    elif (3, 1, 0) <= v < (3, 2, 0):
        return "4.4-all"
    elif (3, 2, 0) <= v <= (3, 2, 1):
        return "4.6-all"
    elif (3, 3, 0) <= v <= (3, 3, 3):
        return "4.10.1-all"
    elif (3, 4, 0) <= v <= (3, 4, 3):
        return "5.1.1-all"
    elif (3, 5, 0) <= v <= (3, 5, 4):
        return "5.4.1-all"
    elif (3, 6, 0) <= v <= (3, 6, 4):
        return "5.6.4-all"
    elif (4, 0, 0) <= v < (4, 1, 0):
        return "6.1.1-all"
    elif (4, 1, 0) <= v: # Any version from 4.1.0 upwards (inclusive)
        # Note: The original code had 4.2.0, but the official table indicates a change at 4.1.0
        return "6.7.1-all" 
    
    # A safe fallback for very old or unhandled future versions.
    return "6.7.1-all"
