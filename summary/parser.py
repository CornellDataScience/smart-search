from typing import List
import requests
import base64

url = r"https://github.com/CornellDataScience/MathSearch"
base_url = r"https://api.github.com/repos/CornellDataScience/MathSearch/contents"


def parse(file_path) -> List[str]:
    import ast

    funcs = []
    full_path = base_url + file_path
    try:
        resp = requests.get(full_path)
        if resp.status_code == requests.codes.ok:
            resp = resp.json()
            content = base64.b64decode(resp["content"])
        else:
            print("Content was not found.")

        tree = ast.parse(content)
        lines = content.decode("utf-8").splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs.append("\n".join(lines[node.lineno - 1 : node.end_lineno]))

    except Exception as e:
        print(f"Error parsing file {file_path}: {e}")

    return funcs


funcs = parse("/lambda-container/lambda_function.py")
print(funcs[0])
