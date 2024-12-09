import os


def collect_requirements(project_path):
    os.system("cd auto_gpt_workspace/{} && detect-requirements . > special_file_1.txt".format(project_path))

def infer_requirements(project_path):
    os.system("cd auto_gpt_workspace/{} && pipreqs . --savepath special_file_2.txt".format(project_path))

def extract_instructions_from_readme(project_path) -> str:
    """
    """
    workspace = "auto_gpt_workspace/"
    files_at_root = os.listdir(os.path.join(workspace, project_path))

    readme_files = []
    for f in files_at_root:
        if "readme" in f.lower():
            readme_files.append(f)

    readme_text = ""

    for f in readme_files:
        with open(os.path.join(workspace, project_path, f)) as wpf:
            readme_text += "------>File: {}\n{}\n".format(f, wpf.read())
    
    if readme_text == "":
        return "No readme file found"
    
    system_prompt = "You are an AI assistant that would help a develper in the mission of installing a python project an getting to run. Your task for now is to analyze the text of the readme file of the target project and extract installation related instructions from the given text of readme file(s)."

    query = "Here is the content of the readme file(s). Please extract any information related to installation including step-by-step points, environement, required software and their versions and also any manaual steps that needs to be done.\n\n" + readme_text[:40000]

    return ask_chatgpt(query, system_prompt)

from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import HumanMessage, SystemMessage, AIMessage
def ask_chatgpt(query, system_message, model="gpt-4o-mini"):
    with open("openai_token.txt") as opt:
        token = opt.read()
    chat = ChatOpenAI(openai_api_key=token, model=model)

    messages = [
        SystemMessage(
            content= system_message
                    ),
        HumanMessage(
            content=query
            )  
    ]
    #response_format={ "type": "json_object" }
    response = chat.invoke(messages)

    return response.content

if __name__ == "__main__":
    print(extract_instructions_from_readme("code2flow"))