"""Commands to call error solving functions"""

COMMAND_CATEGORY = "gradle_build_error_solver"
COMMAND_CATEGORY_TITLE = "Gradle Build Error Solver"

import os
import re
from importlib.resources import files, as_file
import subprocess

from buildAnaDroid.commands.docker_helpers_static import execute_command_in_container
from buildAnaDroid.commands.file_operations import write_to_file
from buildAnaDroid.agents.agent import Agent
from buildAnaDroid.models.command_decorator import command

RES_DIR = "buildAnaDroid.files"
GRADLE_RES_DIR = os.path.join(RES_DIR, "build", "gradle")
GRADLE_WRAPPER_DIR = os.path.join(GRADLE_RES_DIR, "wrapper", "gradle")

def _get_agp_version_from_project(agent: Agent) -> str | None:
    """Scans common build files to find the declared AGP version."""
    build_files_to_check = ["build.gradle.kts", "build.gradle"]
    pattern = re.compile(
        r"""(?:id|classpath)\s*\(?\s*["']com\.android\.(?:application|library|tools\.build:gradle)["']\s*\)?\s*(?:version\s*)?["']([^"']+)["']""",
        re.VERBOSE
    )
    for file_path in build_files_to_check:
        content = execute_command_in_container(agent.shell_socket, f"cat {file_path}")
        if "No such file or directory" in content:
            continue
        match = pattern.search(content)
        if match:
            version = match.group(1)
            print(f"  -> Found AGP version '{version}' in '{file_path}'.")
            return version
    return None

def _update_agp_version_in_file(agent: Agent, file_path: str, target_version: str) -> bool:
    """Safely updates the AGP version in a given Gradle build file."""
    original_content = execute_command_in_container(agent.shell_socket, f"cat {file_path}")
    if "No such file or directory" in original_content:
        return False
    
    # This regex is designed to find the AGP dependency in various forms:
    # 1. `plugins` block: id("com.android.application") version "..."
    # 2. `buildscript` block: "com.android.tools.build:gradle:..."
    # It captures the prefix (group 1) and the suffix (group 3) around the version number.
    pattern = re.compile(
        r"""
        # This is group 1: the prefix before the version number.
        (
            (?: # A non-capturing group for the two alternatives (modern vs. legacy).
                # Alternative 1: Modern plugins block, e.g., id("...") version "..."
                # It looks for 'id(...) version "'
                id\s*\(\s*["']com\.android\.(?:application|library)["']\s*\)\s*version\s*["']
            | 
                # Alternative 2: Legacy buildscript, e.g., classpath "...:gradle:..."
                # It looks for 'classpath "...:gradle:'
                (?:classpath)\s*\(?\s*["']com\.android\.tools\.build:gradle:
            )
        )
        # This is group 2: the actual version string to be replaced.
        ([^"']+)
        # This is group 3: the closing quote that follows the version.
        (["'])
        """,
        re.VERBOSE
    )

    # Replace the old version with the target version
    new_content, count = pattern.subn(rf"\g<1>{target_version}\g<3>", original_content)

    if count > 0:
        print(f"  -> Found and updated AGP version in '{file_path}'.")
        # Safely write the modified content back to the file
        write_to_file(file_path, new_content, agent)
        return True
    return False

def _update_gradle_wrapper(agent: Agent, gradle_version: str) -> bool:
    """Safely updates the Gradle version in gradle-wrapper.properties."""
    wrapper_properties_file = "gradle/wrapper/gradle-wrapper.properties"

    original_content = execute_command_in_container(agent.shell_socket, f"cat {wrapper_properties_file}")
    if "No such file or directory" in original_content:
        return False
    
    # Regex to find and replace the Gradle version in the distributionUrl
    pattern = re.compile(r"(distributionUrl\s*=\s*.*gradle-)[^/]+?(-all\.zip)")
    new_content, count = pattern.subn(rf"\g<1>{gradle_version}\g<2>", original_content)
    
    if count > 0:
        print(f"  -> Updating Gradle Wrapper to version {gradle_version} in '{wrapper_properties_file}'.")
        write_to_file(wrapper_properties_file, new_content, agent)
        return True
    
    print(f"  -> Gradle Wrapper in '{wrapper_properties_file}' is already up-to-date.")
    return False

@command(
    "fix_wrapper_mismatch",
    "Updates the Gradle Wrapper to match the project's AGP version.\nCall if and only if previous output includes 'Failed to notify project evaluation listener'.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def fix_wrapper_mismatch(command: str, agent: Agent):
    print("Attempting to fix WRAPPER_MISMATCH by synchronizing Gradle version...")
    
    # 1. Read the existing AGP version from the project.
    agp_version = _get_agp_version_from_project(agent)
    if not agp_version:
        return "Error: Could not determine the project's AGP version from build files."

    # 2. Determine the corresponding Gradle version.
    required_gradle_version = _get_adequate_gradle_version(agp_version)
    print(f"Project's AGP version {agp_version} requires Gradle ~{required_gradle_version}.")

    # 3. Update the wrapper.
    if _update_gradle_wrapper(agent, required_gradle_version):
        return f"Successfully updated Gradle Wrapper to {required_gradle_version}."
    else:
        return f"Error: Failed to update Gradle Wrapper to version {required_gradle_version}."

@command(
    "import_gradle_wrapper",
    "Copies the entire gradle wrapper template directory into the project.\nCall if and only if previous output includes 'Could not find or load main class org.gradle.wrapper.GradleWrapperMain'.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android Gradle to use",
            "required": True,
        }
    },
)
def import_gradle_wrapper(version: str, agent: Agent):
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
    "Copies the `gradlew` executable script to the project root and makes it executable.\nCall if and only if previous output includes 'gradlew: No such file or directory'.",
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
    "download_sdk_platform",
    "Downloads the missing Android SDK platform.\nCall if and only if previous output includes 'failed to find target with hash string android-<version>'.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android SDK platform to use",
            "required": True,
        }
    },
)
def download_sdk_platform(version: str, agent: Agent):
    print(f"Required platform version: {version}. Attempting download.")
    download_cmd = f"yes | sdkmanager \"platforms;android-{version}\""
    return execute_command_in_container(agent.shell_socket, download_cmd)

@command(
    "download_sdk_build_tools",
    "Downloads the missing Android Build Tools.\nCall if and only if previous output includes 'failed to find Build Tools revision <version>'.",
    {
        "version": {
            "type": "string",
            "description": "The version of the Android SDK Build Tools to use",
            "required": True,
        }
    },
)
def download_sdk_build_tools(version: str, agent: Agent):
    print(f"Required build-tools version: {version}. Attempting download.")
    download_cmd = f"yes | sdkmanager \"build-tools;{version}\""
    return execute_command_in_container(agent.shell_socket, download_cmd)

@command(
    "upgrade_agp_version",
    "Upgrades AGP to a version that supports the `google()` repository shortcut.\nCall if and only if previous output includes 'method google() for arguments'.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def upgrade_agp_version(command: str, agent: Agent):
    print("Attempting to fix GOOGLE_REPO_ERROR by upgrading AGP...")
    min_agp_version = "3.6.3"  # Minimum AGP version that supports google() repository shortcut
    
    # 1. Update the AGP version in all relevant build files.
    print(f"Setting AGP version to a compatible baseline: {min_agp_version}.")
    agp_updated = False
    for build_file in ["build.gradle.kts", "build.gradle"]:
        if _update_agp_version_in_file(agent, build_file, min_agp_version):
            agp_updated = True
    
    if not agp_updated:
        return f"Error: Could not find and update the AGP version to {min_agp_version} in any build file."

    # 2. Now that AGP is updated, call the synchronizer to fix the wrapper.
    # We pass the original command to the next function in the chain.
    print("\nAGP version updated. Now synchronizing Gradle Wrapper...")

    if "Successfully updated" in fix_wrapper_mismatch(command, agent):
        return "Successfully upgraded AGP and synchronized Gradle Wrapper."
    return "Successfully upgraded AGP, but failed to synchronize Gradle Wrapper."

def _add_google_repo_to_file(agent: Agent, file_path: str) -> bool:
    """
    Reads a Gradle file, adds google() to repository blocks if missing,
    and writes the content back.

    Args:
        agent: The agent instance for shell execution.
        file_path: The path to the Gradle file (e.g., 'settings.gradle.kts').

    Returns:
        True if the file was modified, False otherwise.
    """
    # Read the file content from the container
    cat_cmd = f"cat {file_path}"
    original_content = execute_command_in_container(agent.shell_socket, cat_cmd)
    if "No such file or directory" in original_content:
        return False
    
    print(f"Checking for missing google() repo in '{file_path}'...")
    

    # This function is used with re.sub to replace repository blocks.
    # It checks if 'google()' is present and adds it if not.
    def replacer(match):
        # The pattern captures three groups:
        # 1. The opening part: `repositories {`
        # 2. The content inside the braces.
        # 3. The closing brace: `}`
        opening, content, closing = match.groups()
        
        # Check if google() is already present in the block's content.
        # \b ensures we match the whole word 'google'.
        if re.search(r"\bgoogle\(\)", content):
            return match.group(0)  # Return the original, unmodified block
        else:
            # Add google() right after the opening brace with standard indentation.
            # This is much safer than appending to the end of the file.
            print(f"  -> Adding google() to a repositories block in '{file_path}'.")
            # Determine indentation from the line of the opening brace
            start_index = match.start(1)
            line_start_index = original_content.rfind('\n', 0, start_index) + 1
            indentation = original_content[line_start_index:start_index]
            
            # For Kotlin DSL (.kts), a newline is often preferred. For Groovy, it's flexible.
            # Adding it at the top of the block is a common and safe convention.
            return f"{opening}\n{indentation}    google()\n{content}{closing}"

    # The regex finds `repositories { ... }` blocks.
    # It's non-greedy `([\s\S]*?)` to handle multiple repository blocks in one file correctly.
    pattern = re.compile(r"(repositories\s*\{)([\s\S]*?)(\})")
    new_content, num_substitutions = pattern.subn(replacer, original_content)

    if num_substitutions > 0:
        # If changes were made, write the new content back to the file.
        write_to_file(file_path, new_content, agent)
        return True

    return False

@command(
    "add_google_repo",
    "Adds the Google maven repository to the project.\nCall if and only if previous output includes 'Could not resolve all dependencies for configuration'.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def add_google_repo(command: str, agent: Agent):
    print("Attempting to fix MAYBE_MISSING_GOOGLE_REPO...")

    # List of common Gradle files where repositories are defined.
    # Modern Gradle prefers settings.gradle(.kts), so we check those first.
    build_files = [
        "settings.gradle.kts",
        "settings.gradle",
        "build.gradle.kts",
        "build.gradle",
    ]

    was_modified = False
    for file in build_files:
        if _add_google_repo_to_file(agent, file):
            was_modified = True

    if was_modified:
        return "Successfully added google() repository to project configuration."
    else:
        return "No missing google() repository found in any standard Gradle build files; no changes made."

@command(
    "generate_local_properties",
    "Generates a local.properties file with correct SDK and NDK paths from within the container.\nCall if and only if previous output includes 'did not contain a valid NDK and couldn't be used'.",
    {
        "command": {
            "type": "string",
            "description": "The command to execute after fixing the error",
            "required": True,
        }
    },
)
def generate_local_properties(command: str, agent: Agent):
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
    sdk_path = sdk_path_out.strip().split("fi\'\r\n\r")[1] 

    if sdk_path == "SDK_NOT_FOUND" or not sdk_path:
        return f"Error: Could not determine Android SDK path inside the container."
        
    print(f"Discovered SDK path: {sdk_path}")

    # 2. Command to find the latest NDK version directory within the SDK path.
    # `ls -1` lists one file per line. `2>/dev/null` suppresses errors if 'ndk' dir doesn't exist.
    # `tail -n 1` gets the last entry, which is often the latest version.
    find_ndk_cmd = f"sh -c 'ls -1 {sdk_path}/ndk 2>/dev/null | tail -n 1'"
    ndk_version_dir_out = execute_command_in_container(agent.shell_socket, find_ndk_cmd)
    ndk_version_dir = ndk_version_dir_out.strip().split("tail -n 1'\r\n\r")[1]

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
    write_to_file("local.properties", properties_content, agent)

    return "Successfully generated and wrote local.properties."

@command(
    "fix_build_tools_cpu_error",
    "Upgrades the project's Build Tools to a newer version to resolve CPU architecture issues.\nCall if and only if previous output includes 'Bad CPU type in executable'.",
    {
        "version": {
            "type": "string",
            "description": "The version of the build tools to upgrade to",
            "required": True,
        }
    },
)
def fix_build_tools_cpu_error(version: str, agent: Agent):
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

# Helper function to find the AGP version from project files.
def _get_agp_version_from_project(agent: Agent) -> str | None:
    """
    Scans common build files to find the declared Android Gradle Plugin version.
    Returns the version string if found, otherwise None.
    """
    # Check the most common files where AGP version is defined.
    build_files_to_check = ["build.gradle.kts", "build.gradle"]
    
    # Regex to find AGP dependency in both `plugins` and `buildscript` blocks.
    pattern = re.compile(
        r"""
        (?:id|classpath)\s*\(?\s*
        ["']com\.android\.(?:application|library|tools\.build:gradle)["']
        \s*\)?\s*
        (?:version\s*)?
        ["']([^"']+)["']
        """,
        re.VERBOSE
    )

    for file_path in build_files_to_check:
        content = execute_command_in_container(agent.shell_socket, f"cat {file_path}")
        if "no such file or directory" in content:
            continue
        match = pattern.search(content)
        if match:
            version = match.group(1)
            print(f"  -> Found AGP version '{version}' in '{file_path}'.")
            return version
            
    return None

@command(
    "update_gradle_wrapper",
    "Updates the Gradle Wrapper version based on an explicit recommendation in the error log.\nCall if and only if previous output includes 'Minimum supported Gradle version is (.*?)\. Current version'.",
    {
        "error_msg": {
            "type": "string",
            "description": "The error message snippet from the Gradle build: 'Minimum supported Gradle version is (.*?)\. Current version'",
            "required": True,
        }
    },
)
def update_gradle_wrapper(error_msg: str, agent: Agent):
    new_gradle_version = None

    # 1. Primary Method: Try to parse the recommended version from the error message.
    match = re.search(r"Minimum supported Gradle version is (.*?)\. Current version", error_msg)
    if match:
        # The version is group 1. Strip any whitespace. This fixes the "-all" bug.
        recom_v_str = match.group(1).strip()
        new_gradle_version = recom_v_str
        print(f"Found recommended Gradle version in error log: {new_gradle_version}")
    else:
        # 2. Fallback Method: Derive from the project's AGP version.
        print("No direct recommendation found in error log. Attempting to derive from AGP version...")
        agp_version = _get_agp_version_from_project(agent)
        
        if agp_version:
            new_gradle_version = _get_adequate_gradle_version(agp_version)
            print(f"Derived required Gradle version ~{new_gradle_version} from AGP version {agp_version}.")
    
    # 3. Apply the fix if a version was determined.
    if not new_gradle_version:
        return "Error: Could not determine a new Gradle version to use from the error log or project files."

    if _update_gradle_wrapper(agent, new_gradle_version):
        return f"Successfully updated Gradle Wrapper to version {new_gradle_version}."
    else:
        return f"Error: Determined Gradle version should be {new_gradle_version}, but failed to update the wrapper file."
        
def _get_adequate_gradle_version(plugin_version):
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
