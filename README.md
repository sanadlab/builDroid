# ExecutionAgent 🚀  
Automate Building, Testing, and Validation of GitHub Projects in Isolated Containers  

ExecutionAgent is a robust tool leveraging a large language model (LLM) to autonomously **clone, build, install**, and **run test cases** for projects hosted on GitHub—all inside an isolated container. With support for multiple languages and configurations, ExecutionAgent aims to streamline development and quality assurance workflows.  

---

## 📦 Dev Container Setup  
To get started in a VSCode Dev Container:  
1. Install the [Remote - Containers](https://code.visualstudio.com/docs/remote/containers) extension.  
2. Clone this repository.  
3. Open the repository in VSCode, and it will prompt you to reopen in the dev container. Alternatively, use a command to open the current folder in a dev container.  

---

## ✨ Key Features  
- **Dual Mode Execution**: Run ExecutionAgent with a batch file or directly with a GitHub repository URL.  
- **Autonomous Workflow**: Clone, build, and test GitHub projects with no human intervention (we will add human-in-the-loop soon).
- **Language Support**: Multiple languages like Python, C, C++, Java, JavaScript, and more.  
- **Dev Container Integration**: Preconfigured for VSCode Dev Containers for seamless development.  
- **Metrics** (based on evaluation set of 50 projects):  
  - Build Success Rate: **80%**  
  - Test Success Rate: **65%**  

---

## 🚀 How It Works  

### 1️⃣ Single Repository Mode  
You can directly process a single GitHub repository using the `--repo` option:  
```bash
./ExecutionAgent.sh --repo <github_repo_url>
```  
Example:  
```bash
./ExecutionAgent.sh --repo https://github.com/pytest-dev/pytest
```  

When this mode is used, ExecutionAgent will:  
1. Extract the project name from the URL.  
2. Determine the repository's primary programming language by calling `get_main_language.py`.  
3. Clone the repository and set up metadata.  
4. Launch the main loop of ExecutionAgent to build the project and run its test cases.  

### 2️⃣ Batch File Mode  
Prepare a batch file listing projects to process in the format:  
`<project_name> <github_url> <language>`  

Example (notice how for now we leave one empty line after each entry):  
```plaintext
scipy https://github.com/scipy/scipy Python

pytest https://github.com/pytest-dev/pytest Python

```

Run ExecutionAgent with the batch file:  
```bash
./ExecutionAgent.sh /path/to/batch_file.txt
```  
ExecutionAgent will process each project listed in the file, performing the same steps as the single repository mode.

---

## 🔧 Configuration 

**More options on configuring the agent would be coming soon**

---

## 📊 Results Summary  

| **Metric**              | **Success Rate** |  
|--------------------------|------------------|  
| Build Success Rate       | 80%              |  
| Test Execution Rate      | 65%              |  

Results are logged under `experimental_setups/experiment_XX`, where `XX` is an incremented number for each invocation of ExecutionAgent.  

---

## 📜 Research Paper  
Dive into the technical details and evaluation in our [paper](link to paper).  

---

## 📬 Feedback  
Have suggestions or found a bug? Open an issue or contact us at [my_email](mailto:fi_bouzenia@esi.dz).