from typing import List
import ollama
from pydantic import BaseModel
import os 
import requests
import json 
import base64

base_url = r"https://github.com/CornellDataScience/MathSearch"
content_base_url = r"https://api.github.com/repos/CornellDataScience/MathSearch/contents"

class SummaryResult(BaseModel):
    summary: str
    code: str
    metadata: dict

EMPTY_RESULT = SummaryResult(summary="", code="", metadata={})

class ContextAwareFunctionSummaryGenerator: 
    '''
    This module aims to generate a summary for each function in a repository. Only python files are supported. 
    To make the summary generation of each function context aware, we do a depth first search on the file system tree and appending the context for each 
    step of the traversal. The run function runs the whole module and stores the results in self.summaries. 
    '''
    def __init__(self, base_url, content_base_url):
        self.base_url = base_url
        self.content_base_url = content_base_url
        self.summaries: List[SummaryResult] = []

    def request_file_content(self, file_path):
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

    
    def process_python_file(self, context: str, path: str) -> List[SummaryResult]:
        '''
        called when the traversal encounters a file.
        calls self.parse to parse the file into list of function, summarizes each function, and store them in self.summaries. 
        '''
        if not path.endswith('.py'):
            return [EMPTY_RESULT]
        
        try:
            file_content = self.request_file_content(path)
            functions = self.parse(file_content)
            
            # Add file-specific information to context
            file_context = f"{context}\nFile: {path}\n"
            results = []
            for func in functions:
                summary_result = self.summarize(file_context, func)
                results.append(summary_result)
            return results
                
        except Exception as e:
            print(f"Error processing file {path}: {e}")

    def extract_context_from_summaries(summaries : List[SummaryResult]) -> str:
        '''
        Extracts the context from the summaries
        '''
        context = "There exist functions in the parent directory that does the following: \n"
        for summary in summaries:
            context += summary.summary + "\n"
        return context
        
    def process_dir(self, context: List[str], path: str):
        full_path = self.content_base_url + path
        print("Processing directory:", full_path)

        resp = requests.get(full_path)
        if resp.status_code == requests.codes.ok:
            contents = resp.json()
        else:
            print(f"Content was not found at path {full_path}")

        readme_file = next((item for item in contents if item["name"].lower().startswith("readme")), None)
        if readme_file:
            readme_file_content = self.request_file_content(f"{path}/{readme_file['name']}")
            print(readme_file_content)
            context += readme_file_content

        for item in contents:
            if item["type"] == "dir":
                self.process_dir(context, f"{path}/{item['name']}")
            else:
                self.process_python_file(context, f"{path}/{item['name']}")


    def parse(self, file_content) -> List[str]:
        '''
        file_content should be a string of valid python code
        '''
        import ast

        funcs = []

        tree = ast.parse(file_content)
        lines = file_content.decode("utf-8").splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs.append("\n".join(lines[node.lineno - 1 : node.end_lineno]))

        return funcs


    def summarize(self, context: str, target: str) -> SummaryResult:
        try:
            response = ollama.generate(
                model="llama3.1:latest",
                prompt=context + target,
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


def main():
    summarizer = ContextAwareFunctionSummaryGenerator(base_url, content_base_url)
    summarizer.run()
    # result = summarizer.summarize("create a short natural language summary of the function", "def add(a, b):\n    return a + b")
    # print(result.metadata)
    # print(result.code)
    # print(result.summary)

    #print first 5 summaries

if __name__ == "__main__":
    main()