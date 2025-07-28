# BuilDroid

[![PyPI version](https://badge.fury.io/py/buildroid.svg)](https://badge.fury.io/py/buildroid)
[![PyPI license](https://img.shields.io/pypi/l/ansicolortags.svg)](https://pypi.python.org/pypi/buildroid)
[![PyPI status](https://img.shields.io/pypi/status/ansicolortags.svg)](https://pypi.python.org/pypi/buildroid)

⚡ Clone, build, and generate debugging APKs for Android projects using LLM-powered automation.

**BuilDroid** is a Python package that leverages Large Language Models (LLMs) to automatically clone any Android project hosted on GitHub, configure it, and **build the debugging `.apk`** file. This enables faster evaluation, performance testing, reverse engineering, or security analysis of Android applications. The building process happens in an isolated Docker container.

## 🚀 Features

- 🔗 Clone any Android GitHub repository.
- ⚙️ Auto-configure Gradle build for debugging.
- 🤖 LLM-guided build troubleshooting and error recovery.
- 📦 Outputs ready-to-install **debugging APK**.
- 🧪 Supports workflows for performance evaluation and static/dynamic analysis.

## 📦 Installation

```bash
pip install buildroid
```

## 📦 Dev Container Setup  

To setup in a VSCode Dev Container:  
1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.  
2. Clone this repository. 
3. Open the repository in VSCode, and it will prompt you to reopen in the dev container. Alternatively, use a command to open the current folder in a dev container.

## ✅ Requirements

* Python 3.10+
* Git installed and accessible from terminal
* OpenAI API key (or other LLM provider) for LLM access.

## ⚙️ LLM Configuration

`builDroid` uses an LLM backend for build assistance. To use it:

1. Obtain your API key from OpenAI or compatible provider.
2. Set your API key as a .env file:

```.env
API_KEY=<your-api-key-here>
BASE_URL=<your-base-url-here>
LLM_MODEL=<your-llm-model-here>
```

`BASE_URL` and `LLM_MODEL` are optional. If not provided, `builDroid` will use OpenAI's `gpt-4.1-mini-2025-04-14`.
For example, if you put 'https://generativelanguage.googleapis.com/v1beta/' as your base url, `builDroid` will access Google AI's `gemini-2.0-flash-lite`.
If you want to use other providers, you have to provide the base url and the LLM model in `.env`.

3. (Optional) builDroid's primary goal is to successfully execute `./gradlew assembleDebug`. To change its goals, create a `ai_settings.yaml` file in the working directory. The example file is in the source code.

## 🖥️ Usage

### CLI Usage

```bash
buildroid build https://github.com/user/project # Run on a single repository
buildroid build repos.txt # Run on a list of repositories from a file
buildroid build local_path --local # Run with a local repository
```
```bash
buildroid clean # Clean test results
```

### Advanced Options for Builds

* `-n`, `--num`: Specify cycle limit (max. number of commands to execute)
* `-c`, `--conv`: Enable conversation mode (API works with conversation models)
* `-k`, `--keep-container`: Keep container after build (builDroid removes container by default)
* `-l`, `--local`: Build from a local repository (Provide local path instead of Github link)

### Python Usage

```python
import builDroid

# You must load environment variables separately for Python usage

source = "https://github.com/user/project"
builDroid.process_repository(repo_source=source)
# args: 
# repo_source: str, num: int=40, conversation: bool=False, extract_project: bool=True, keep_container:bool=False, user_retry:bool=False, local_path:bool=False
```

## 🛠️ Troubleshooting

If the build fails, `builDroid` will attempt to:

1. Analyze the error output.
2. Query the LLM for common solutions.
3. Retry the build with suggested fixes.

> ❗ **Note:** Some complex/outdated builds may still require manual intervention.

## 🏗️ Roadmap

* [ ] Integration with emulator for automated APK testing

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss.

## 📜 License

MIT License. See `LICENSE` for details.

## 🙏 Acknowledgments

* OpenAI for LLM API
* ExecutionAgent
