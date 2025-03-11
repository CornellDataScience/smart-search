from typing import List

GITHUB_API_BASE = "https://api.github.com/repos/CornellDataScience/MathSearch/contents"


def process_dir(context: List[str], path: str):
    contents = parse(path)

    readme_file = next((item for item in contents if item["name"].lower().startswith("readme")), None)
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
