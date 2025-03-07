from typing import List
import ollama
from pydantic import BaseModel
import os 
import json 

class SummaryResult(BaseModel):
    summary: str
    code: str
    metadata: dict

class ContextAwareFunctionSummaryGenerator: 
    '''
    This module aims to generate a summary for each function in a repository. Only python files are supported. 
    To make the summary generation of each function context aware, we do a depth first search on the file system tree and appending the context for each 
    step of the traversal. The run function runs the whole module and stores the results in self.vectors. 
    '''
    def __init__(self, ROOT, api):
        self.ROOT = ROOT
        self.api = api # api can be github api or local file system
        self.vectors: List[SummaryResult] = []
    
    def process_file(self, context: str, path: str):
        '''
        called when the traversal encounters a file.
        calls self.parse to parse the file into list of function, summarizes each function, and store them in self.vectors. 
        '''
        if not path.endswith('.py'):
            return
        
        try:
            functions = self.parse(path)
            
            # Add file-specific information to context
            file_context = f"{context}\nFile: {path}\n"
            
            for func in functions:
                summary_result = self.summarize(file_context, func)
                self.vectors.append(summary_result)
                
        except Exception as e:
            print(f"Error processing file {path}: {e}")

    def process_dir(self, context: str, path: str): 
        '''
        called when the traversal encounters a directory
        processes the directory. 
        Calls process file for .py files in the directory.
        Uses current files's context and relavant documentation to enrich the context. 
        Calls process_dir on subdirectories with the enriched context. 
        '''
        import os
        
        try:
            # Enhance context with directory information
            dir_context = f"{context}\nDirectory: {path}\n"
            
            # Look for README or documentation to enhance context
            readme_path = os.path.join(path, "README.md")
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, 'r') as f:
                        readme_content = f.read()
                    dir_context += f"\nREADME: {readme_content}\n"
                except Exception as e:
                    print(f"Error reading README {readme_path}: {e}")
            
            # Process all items in the directory
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                
                # Skip hidden files and directories
                if item.startswith('.'):
                    continue
                
                if os.path.isfile(item_path):
                    self.process_file(dir_context, item_path)
                elif os.path.isdir(item_path):
                    self.process_dir(dir_context, item_path)
                    
        except Exception as e:
            print(f"Error processing directory {path}: {e}")

    def parse(self, file_path) -> List[str]: 
        '''
        parse a .py file using the AST module into a list of strings, each string
        containing the code of a function 
        '''
        import ast
        
        functions = []
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
                
            tree = ast.parse(file_content)
            lines = file_content.splitlines()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Get start line (1-based indexing in AST, convert to 0-indexed)
                    start_line = node.lineno - 1
                    
                    # Find function end based on indentation
                    base_indent = None
                    end_line = len(lines)
                    
                    # Get the indentation of the function definition line
                    first_line = lines[start_line]
                    base_indent = len(first_line) - len(first_line.lstrip())
                    
                    # Find the end of the function
                    for i, line in enumerate(lines[start_line + 1:], start_line + 1):
                        if not line.strip() or line.strip().startswith('#'):
                            continue
                            
                        curr_indent = len(line) - len(line.lstrip())
                        if curr_indent <= base_indent:
                            end_line = i
                            break
                    
                    function_code = '\n'.join(lines[start_line:end_line])
                    functions.append(function_code)
                    
        except Exception as e:
            print(f"Error parsing file {file_path}: {e}")
            
        return functions

    def summarize(self, context: str, target: str) -> SummaryResult:
        '''
        @params: 
        context: contextual information about the codebase
        target: the function string to be summarized
        Use LLM to summarize the target 
        '''
        prompt = f"""
        Given the following context about a codebase:
        {context}
        
        Please provide a concise summary for this function:
        ```python
        {target}
        ```
        
        Provide a clear description of:
        1. What the function does (purpose)
        2. Input parameters and their types
        3. Return value and type
        4. Any side effects
        5. How it relates to the rest of the codebase based on the context
        
        Format your response as a concise paragraph.
        """
        
        try:
            response = ollama.generate(
                model="codellama",
                prompt=prompt,
                temperature=0.2,
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
        print(f"Starting code summary generation for repository: {self.ROOT}")
        
        initial_context = f"Repository: {self.ROOT}\n"
        
        # Start processing from the root directory
        self.process_dir(initial_context, self.ROOT)
        
        print(f"Generated {len(self.vectors)} function summaries")


def main():
    # Repository path to analyze
    repo_path = os.path.abspath("./your_target_repository")
    
    # Initialize the summary generator
    # Using None for api since we're working with local filesystem
    generator = ContextAwareFunctionSummaryGenerator(ROOT=repo_path, api=None)
    
    # Run the summary generation process
    generator.run()
    
    print(f"Summary generation complete. Found {len(generator.vectors)} functions.")
    
    # Save the results to a JSON file
    results = [
        {
            "summary": item.summary,
            "code": item.code,
            "file_path": item.metadata.get("context", "").split("File: ")[-1].split("\n")[0] if "File: " in item.metadata.get("context", "") else "unknown",
            "repository": repo_path
        }
        for item in generator.vectors
    ]
    
    # Save to file
    output_file = "function_summaries.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Saved {len(results)} function summaries to {output_file}")
    
    # Display a few examples
    print("\nSample summaries:")
    for i, result in enumerate(results[:3]):
        print(f"\n--- Function {i+1} ---")
        print(f"File: {result['file_path']}")
        print(f"Summary: {result['summary'][:150]}...")

if __name__ == "__main__":
    main()