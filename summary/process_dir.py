from typing import List
import requests
import base64
content_base_url = "https://api.github.com/repos/CornellDataScience/MathSearch/contents"

def process_file(context: List[str], path: str): pass 

def process_dir(context: List[str], path: str):
    full_path = content_base_url + path
    resp = requests.get(full_path)
    if resp.status_code == requests.codes.ok:
        contents = resp.json()
    else:
        print("Content was not found.")

    readme_file = next((item for item in contents if item["name"].lower().startswith("readme")), None)
    print(readme_file)
    if readme_file:
        context.append(process_file(f"{path}/{readme_file['name']}"))
        return


    for item in contents:
        if item["type"] == "dir":
            process_dir(context, f"{path}/{item['name']}")
        else:
            process_file(context, f"{path}/{item['name']}")

context = []
process_dir(context, "")
summary = "\n\n".join(context)
print(summary)

# resp = requests.get(content_base_url).json()
# contents = base64.b64decode(resp["content"])
# print(contents)

