from typing import List, Dict, Optional
import ollama
from pydantic import BaseModel
import os 
import requests
import json 
import base64
from enum import Flag, auto

base_url = "mathsearch"
content_base_url = "mathsearch"
class SummaryResult(BaseModel):
    name: str
    summary: str
    code: str
    metadata: dict
    type: Optional[str] = None  # Add type field

class ItemTypes(Flag): 
    PYTHON_FILE = auto()
    DIRECTORY = auto()
    README_FILE = auto()
    OTHER = auto()
class Node: 
    def __init__(self, name: str, node_type: ItemTypes, path: str, summaries: List[SummaryResult] = None, 
                 final_summary: SummaryResult = None, children: List['Node'] = None, 
                 parent: Optional['Node'] = None): 
        self.name = name
        self.type = node_type
        self.path = path
        self.summaries = summaries or []
        self.final_summary = final_summary
        self.children = children or []
        self.parent = parent



EMPTY_RESULT = SummaryResult(name="", summary="", code="", metadata={})

class ContextAwareFunctionSummaryGenerator: 
    '''
    This module aims to generate a summary for each function in a repository. Only python files are supported. 
    To make the summary generation of each function context aware, we do a depth first search on the file system tree and appending the context for each 
    step of the traversal. The run function runs the whole module and stores the results in self.summaries. 
    '''
    def __init__(self, base_url, content_base_url):
        self.using_api = False
        self.base_url = base_url
        self.function_prompt = "create a short natural language summary of the function"
        self.directory_prompt = "create a short natural language summary of the directory"
        self.file_prompt = "create a short natural language summary of the file"
        self.context_prompt = "create a short natural language summary of the context"
        self.content_base_url = content_base_url
        self.root: Node 
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
        try:
            with open(file_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
        
    def get_file_content(self, file_path):
        if self.using_api:
            return self.request_file_content(file_path)
        else:
            content = self.read_file_content(file_path)
            if content is None:  # Check if file was found
                print(f"File not found: {file_path}")
                return None
            return content
        
        
                
    def extract_context_from_function_summaries(self, summaries: List[SummaryResult]) -> str: 
        # Aggregate all function summaries for the LLM to generate a file summary
        context = "Here are summaries of all functions in this file:\n\n"
        for summary in summaries:
            context += f"Function {summary.name}:\n{summary.summary}\n\n"
        return context

    def extract_context_from_directory_summaries(self, summaries: List[SummaryResult]) -> str:
        # Aggregate all child summaries for the LLM to generate a directory summary
        context = "Here are summaries of all items in this directory:\n\n"
        for summary in summaries:
            if summary.type == "DIRECTORY":
                context += f"Directory {summary.name}:\n{summary.summary}\n\n"
            else:
                context += f"File {summary.name}:\n{summary.summary}\n\n"
        return context

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
            # For file type checks, use just the item name
            item_name = os.path.basename(item)
            if item_name.endswith(".py"):
                return ItemTypes.PYTHON_FILE
            elif item_name.lower().startswith("readme"):
                return ItemTypes.README_FILE
            elif os.path.isdir(item):  # For directory check, use the full path
                return ItemTypes.DIRECTORY
            else:
                return ItemTypes.OTHER

    def item_name(self, item) -> str:
        if self.using_api:
            return item["name"]
        else:
            return item
        
    

    def parse(self, file_content) -> List[Dict[str, str]]:
        '''
        file_content should be a string of valid python code
        Returns a list of dictionaries containing function name and code
        '''
        import ast

        funcs = []
        try:
            tree = ast.parse(file_content)
            lines = file_content.splitlines()

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    funcs.append({
                        "name": node.name,  # Get the function name
                        "code": "\n".join(lines[node.lineno - 1 : node.end_lineno])
                    })
            return funcs
        except Exception as e:
            print(f"Error parsing file: {e}")
            return []



  
    def summarize_function(self, target_code: str, name: str) -> SummaryResult:
        try:
            print(f"Generating summary for function: {name}")
            
            response = ollama.generate(
                model="llama3.2:latest",
                prompt= self.function_prompt + "\n" + target_code,
                stream = False,
                options={'num_predict': -1, 'keep_alive': 0},
            )
            
            summary = response['response'].strip()
            
            return SummaryResult(
                name=name,
                summary=summary,
                code=target_code,
                metadata={}
            )
        except Exception as e:
            print(f"Error generating summary: {e}")
            return SummaryResult(
                name=name,
                summary=f"Error generating summary: {str(e)}",
                code=target_code,
                metadata={"error": str(e)}
            )
    def summarize_file(self, target_summaries: str, name: str) -> SummaryResult:
        try:
            response = ollama.generate(
                model="llama3.2:latest",
                prompt= self.file_prompt + target_summaries,
                stream = False,
                options={'num_predict': -1, 'keep_alive': 0},
            )
            summary = response['response'].strip()
            return SummaryResult(
                name=name,
                summary=summary,
                code="",  # Keep the raw code for files
                metadata={}
            )
        except Exception as e:
            print(f"Error generating summary: {e}")
            return SummaryResult(
                name=name,
                summary=f"Error generating summary: {str(e)}",
                code=target_summaries,  # Keep the raw code for files
                metadata={"error": str(e)}
            )
    def summarize_directory(self, target_summaries: str, name: str) -> SummaryResult:
        try:
            response = ollama.generate(
                model="llama3.2:latest",
                prompt= self.directory_prompt + target_summaries,
                stream = False,
                options={'num_predict': -1, 'keep_alive': 0},
            )
            summary = response['response'].strip()
            return SummaryResult(
                name=name,
                summary=summary,
                code="",  # Always empty string for directories
                metadata={}
            )
        except Exception as e:
            print(f"Error generating summary: {e}")
            return SummaryResult(
                name=name,
                summary=f"Error generating summary: {str(e)}",
                code="",  # Always empty string for directories
                metadata={"error": str(e)}
            )
    def make_context(self, context: str, summary: str) -> str:
        try:
            response = ollama.generate(
                model="llama3.2:latest",
                prompt= self.context_prompt + context + summary,
                stream = False,
                options={'num_predict': -1, 'keep_alive': 0},
            )
            return response['response'].strip()
        except Exception as e:
            print(f"Error generating context: {e}")
            return ""
        
    def get_directory_content(self, path):
        if self.using_api:
            full_path = self.content_base_url + path
            resp = requests.get(full_path)
            if resp.status_code == requests.codes.ok:
                return resp.json()
            else:
                print("Content was not found.")
                return {}
        else: 
            try:
                print(f"Listing directory: {path}")
                items = os.listdir(path)
                print(f"Found items: {items}")
                return items
            except Exception as e:
                print(f"Error listing directory {path}: {e}")
                return []



    def process_python_file(self, content: str) -> List[SummaryResult]:
        if content is None:  # Skip if file wasn't found
            return []
        print("Parsing functions...")
        functions = self.parse(content)
        print("Functions parsed:", len(functions))
        results = []
        for func in functions:
            summary_result = self.summarize_function(func["code"], func["name"])
            results.append(summary_result)
            print(f"summarized function {func['name']}: {summary_result.summary}")
            print("-" * 20)
        return results

    def process_dir(self, node: Node, path: str):
        '''
        Processes a directory and adds its contents to the tree
        '''
        print(f"\nProcessing directory: {path}")
        contents = self.get_directory_content(path)
        print(f"Contents: {contents}")
        
        if not contents:
            print(f"No contents found in directory: {path}")
            return

        for item in contents: 
            print(f"\nProcessing item: {item}")
            item_path = os.path.join(path, item)
            item_type = self.item_type(item_path)  # Pass the full path instead of just the item name
            print(f"Item type: {item_type}")
            item_name = self.item_name(item)
            
            child_node = Node(
                name=item_name,
                node_type=item_type,
                path=item_path,
                summaries=[],
                final_summary=EMPTY_RESULT,
                children=[],
                parent=node
            )
            
            if item_type == ItemTypes.PYTHON_FILE:
                print(f"Processing Python file: {item_path}")
                file_content = self.get_file_content(item_path)
                if file_content is not None:
                    print("File content loaded successfully")
                    summaries = self.process_python_file(file_content)
                    child_node.summaries = summaries
                    # Get function summaries for file summary
                    final_summary_target = self.extract_context_from_function_summaries(summaries)
                    final_summary = self.summarize_file(final_summary_target, item_name)
                    final_summary.code = file_content  # Store raw file content
                    final_summary.type = "PYTHON_FILE"  # Set type
                    child_node.final_summary = final_summary
                    node.children.append(child_node)
                else:
                    print(f"Failed to load file content for: {item_path}")
            elif item_type == ItemTypes.README_FILE:
                print(f"Processing README file: {item_path}")
                file_content = self.get_file_content(item_path)
                if file_content is not None:
                    print("File content loaded successfully")
                    final_summary = self.summarize_file(file_content, item_name)
                    final_summary.code = file_content  # Store raw file content
                    final_summary.type = "README_FILE"  # Set type
                    child_node.final_summary = final_summary
                    child_node.summaries = [child_node.final_summary]
            elif item_type == ItemTypes.DIRECTORY:
                print(f"Processing directory: {item_path}")
                self.process_dir(child_node, item_path)
                node.children.append(child_node)

        # Collect all final summaries from children
        summariesfromnode = []
        for child in node.children:
            if child.final_summary and child.final_summary != EMPTY_RESULT:
                summariesfromnode.append(child.final_summary)
        
        if summariesfromnode:  # Only generate directory summary if there are child summaries
            final_summary_target = self.extract_context_from_directory_summaries(summariesfromnode)
            final_summary = self.summarize_directory(final_summary_target, node.name)
            final_summary.type = "DIRECTORY"  # Set type
            node.final_summary = final_summary
        return node
                

    def build_intial_tree(self):
        '''
        Builds the tree of the repository
        '''
        root_node = Node(
            name="root",
            node_type=ItemTypes.DIRECTORY,
            path="",
            summaries=[],
            final_summary=EMPTY_RESULT,
            children=[],
            parent=None
        )
        self.root = root_node
    def run(self): 
        self.build_intial_tree()
        # Start processing from the current directory
        self.process_dir(self.root, self.base_url)
        return self.root
    def dumps(self) -> str:
        """
        Traverses the tree and converts the entire structure to a JSON string
        """
        def node_to_dict(node: Node):
            """Convert a node and its children to a dictionary"""
            result = {
                "name": node.name,
                "type": node.type.name,
                "path": node.path,
                "summaries": [summary.dict() for summary in node.summaries],
                "final_summary": node.final_summary.dict() if node.final_summary else None,
                "children": []
            }
            
            for child in node.children:
                result["children"].append(node_to_dict(child))
            
            return result
        
        # Convert the entire tree to a dictionary
        tree_dict = node_to_dict(self.root)
        
        # Convert to JSON string with pretty printing
        return json.dumps(tree_dict, indent=2)

def main():
    print("Starting summary generation...")
    generator = ContextAwareFunctionSummaryGenerator(base_url, content_base_url)
    print("Processing repository...")
    generator.run()
    print("Generating JSON output...")
    
    # Save the output to a JSON file
    json_output = generator.dumps()
    with open("summary_output.json", "w") as f:
        f.write(json_output)
    print("Done! Output saved to summary_output.json")

if __name__ == "__main__":
    main()

