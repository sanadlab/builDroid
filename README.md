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
- **Autonomous Workflow**: Clone, build, and test GitHub projects with minimal human intervention.  
- **Language Support**: Detect and manage projects in Python, C, C++, Java, JavaScript, and more.  
- **Dev Container Integration**: Preconfigured for VSCode Dev Containers for seamless development.  
- **Metrics** (based on evaluation set of 50 projects):  
  - Build Success Rate: **80%**  
  - Test Success Rate: **65%**  
- **Flexible Execution**: Handle multiple projects from a single batch file or multiple batches at once.  

---

## 🚀 How It Works  

### 1️⃣ Input Batch File  
Prepare a batch file listing projects to process in the format:  
`<project_name> <github_url> <language> <container_name>`  

Example:  
```plaintext
scipy https://github.com/scipy/scipy Python scipy_image:rundex
```

### 2️⃣ Run ExecutionAgent  
Use the following command to process the batch file (assuming the batch file is inside the folder nightly_runs):  
```bash
./rundex.sh nightly_runs/batch_2.txt
```  
When run for the first time, the command will install the dependencies needed for ExecutionAgent and prompt the user for a OpenAI token.

### 3️⃣ Output  
For each project, ExecutionAgent will:  
- Clone the repository  
- Identify and set up required dependencies  
- Build the project  
- Run its test cases  
Results are logged under experimental_setups/experiment_XX (XX is an integer incremented with each new invocation of the tool, i.e, new call to ./rundex.sh ...)  

---

## 🔧 Configuration  
- Comming soon

---

## 📊 Results Summary  

| **Metric**              | **Success Rate** |  
|--------------------------|------------------|  
| Build Success Rate       | 80%              |  
| Test Execution Rate      | 65%              |  

---

## 📜 Research Paper  
Dive into the technical details and evaluation in our [paper](link to paper).  

---

## 📬 Feedback  
Have suggestions or found a bug? Open an issue or contact us at [my_email](mailto:fi_bouzenia@esi.dz).  

