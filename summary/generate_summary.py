from typing import List
import ollama
from pydantic import BaseModel
import os 
import requests
import json 
import base64
from enum import Flag, auto

base_url = r"https://github.com/CornellDataScience/MathSearch"
content_base_url = r"https://api.github.com/repos/CornellDataScience/MathSearch/contents"

class SummaryResult(BaseModel):
    summary: str
    code: str
    metadata: dict

class ItemTypes(Flag): 
    PYTHON_FILE = auto()
    DIRECTORY = auto()
    README_FILE = auto()
    OTHER = auto()

EMPTY_RESULT = SummaryResult(summary="", code="", metadata={})

class ContextAwareFunctionSummaryGenerator: 
    '''
    This module aims to generate a summary for each function in a repository. Only python files are supported. 
    To make the summary generation of each function context aware, we do a depth first search on the file system tree and appending the context for each 
    step of the traversal. The run function runs the whole module and stores the results in self.summaries. 
    '''
    def __init__(self, base_url, content_base_url):
        self.using_api = False
        self.base_url = base_url
        self.base_prompt = "create a short natural language summary of the function"
        self.content_base_url = content_base_url
        self.summaries: List[SummaryResult] = []

    def request_file_content(self, file_path):
        '''
        requests file content from the github api path self.content_base_url + file_path and returns the file content as a string
        '''
        try:
            full_path = self.content_base_url + file_path
            resp = requests.get(full_path)
            if resp.status_code == requests.codes.ok:
                resp = resp.json()
                byte_content = base64.b64decode(resp["content"])
                return byte_content.decode("utf-8")
            else:
                print("Content was not found.")
                return "Content Not Found"
        except Exception as e:
            print(f"Error requesting file {file_path}: {e}")
            return "Content Not Found"

    def read_file_content(self, file_path):
        '''
        reads file content from the local file system and returns the file content as a string
        '''
        full_path = self.content_base_url + file_path
        try:
            with open(full_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            return "Content Not Found"
        
    def get_file_content(self, file_path):
        if self.using_api:
            return self.request_file_content(file_path)
        else:
            return self.read_file_content(file_path)
        
        
    def process_python_file(self, context: str, content: str) -> List[SummaryResult]:
        '''
        called when the traversal encounters a file.
        Requires: content is a string of valid python code
        calls self.parse to parse the file into list of function, summarizes each function, and store them in self.summaries. 
        '''
        print("Parsing functions...")
        functions = self.parse(content)
        print("Functions parsed:", len(functions))
        # Add file-specific information to context
        file_context = f"Context: {context}"
        results = []
        for func in functions:
            summary_result = self.summarize(file_context, func)
            results.append(summary_result)
            print(f"summarized function: {summary_result.summary}")
            print("-" * 20)
        return results
                
    def extract_context_from_summaries(summaries : List[SummaryResult]) -> str:
        '''
        Extracts the context from the summaries
        '''
        context = "There exist functions in the parent directory that does the following: \n"
        for summary in summaries:
            context += summary.summary + "\n"
        return context
        
    def get_directory_content(self, path):
        full_path = self.content_base_url + path
        if self.using_api:
            resp = requests.get(full_path)
            if resp.status_code == requests.codes.ok:
                return resp.json()
            else:
                print("Content was not found.")
                return {}
        else: 
            item_paths = []
            for item in os.listdir(full_path):
                item_paths.append(os.path.join(full_path, item))
            return item_paths

    def item_type(self, item) -> ItemTypes:
        if self.using_api:
            if item["type"] == "file":
                if item["name"].endswith(".py"):
                    return ItemTypes.PYTHON_FILE
                elif item["name"].lower().startswith("readme"):
                    return ItemTypes.README_FILE
                else:
                    return ItemTypes.OTHER
            elif item["type"] == "dir":
                return ItemTypes.DIRECTORY
            else:
                raise ValueError("Unknown item type, not directory or file")
            
        else:
            # item here is full path of the item
            if os.path.isdir(item): 
                return ItemTypes.DIRECTORY
            elif os.path.isfile(item):
                if item.endswith(".py"):
                    return ItemTypes.PYTHON_FILE
                elif item.lower().startswith("readme"):
                    return ItemTypes.README_FILE
                else:
                    return ItemTypes.OTHER
            else:
                print(f"Unknown item type: {item}")
                raise ValueError("Unknown item type, not directory or file")

    def item_name(self, item) -> str:
        if self.using_api:
            return item["name"]
        else:
            # item here is full path of the item, so we need to get the base name
            # print(f"getting basename of item {item}")
            # print(f'item name: {os.path.basename(item)}')
            return os.path.basename(item)
        
    def process_dir(self, context: List[str], path: str):
        print("Processing directory:", path)
        contents = self.get_directory_content(path)
        if not contents:
            return

        readme_file = next((item for item in contents if self.item_type(item) == ItemTypes.README_FILE), None)
        if readme_file:
            readme_file_content = self.get_file_content(f"{path}/{self.item_name(readme_file)}")
            print(readme_file_content)
            context += readme_file_content

        for item in contents:
            if self.item_type(item) == ItemTypes.DIRECTORY:
                self.process_dir(context, f"{path}/{self.item_name(item)}")
            elif self.item_type(item) == ItemTypes.PYTHON_FILE:
                file_content = self.get_file_content(f"{path}/{self.item_name(item)}")
                print(f"Processing file: {self.item_name(item)}")
                try: 
                    self.summaries += self.process_python_file(context, file_content)
                except Exception as e:
                    print(f"Error processing file {self.item_name(item)}: {e}")

    def parse(self, file_content) -> List[str]:
        '''
        file_content should be a string of valid python code
        '''
        import ast

        funcs = []

        tree = ast.parse(file_content)
        lines = file_content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs.append("\n".join(lines[node.lineno - 1 : node.end_lineno]))

        return funcs


    def summarize(self, context: str, target: str) -> SummaryResult:
        try:
            #print(f"prompt: {self.base_prompt + context + target}")
            print("Generating summary...")
            
            response = ollama.generate(
                model="llama3.1:latest",
                prompt= self.base_prompt + context + target,
                stream = False,
                options={'num_predict': -1, 'keep_alive': 0},
            )
            
            summary = response['response'].strip()
            
            return SummaryResult(
                summary=summary,
                code=target,
                metadata={"context": context}
            )
        except Exception as e:
            print(f"Error generating summary: {e}")
            return SummaryResult(
                summary=f"Error generating summary: {str(e)}",
                code=target,
                metadata={"context": context, "error": str(e)}
            )

    def run(self) -> None: 
        '''
        runs the whole workflow
        '''
        print(f"Starting code summary generation for repository: {self.content_base_url}")
        
        initial_context = f"Repository: {self.content_base_url}\n"
        
        # Start processing from the root directory
        self.process_dir(initial_context, "")
        
        print(f"Generated {len(self.summaries)} function summaries")

    def dumps(self) -> str:
        '''
        dumps the summaries into a json string
        '''
        return json.dumps([summary.dict() for summary in self.summaries])

def main():
    summarizer = ContextAwareFunctionSummaryGenerator("./data/MathSearch", "./data/MathSearch")
    summarizer.run()
    #save as json file
    with open("summaries.json", "w") as f:
        f.write(summarizer.dumps())

    # for item in os.listdir("./summary"):
    #     if os.path.isfile("./summary/" + item):
    #         print(f"{item} is a file")
    #     elif os.path.isdir(item):
    #         print(f"{item} is a directory")
    #     else:
    #         print(f"{item} is of unknown type")

    # result = summarizer.summarize("create a short natural language summary of the function", "def add(a, b):\n    return a + b")
    # print(result.metadata)
    # print(result.code)
    # print(result.summary)

    #print first 5 summaries

if __name__ == "__main__":
    main()