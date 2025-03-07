from typing import List
import ollama
from pydantic import BaseModel

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
    
    def process_file(self, context, path):
        '''
        called when the traversal encounters a file.
        calls self.parse to parse the file into list of function, summarizes each function, and store them in self.vectors. 
        '''
        pass

    def process_dir(self, context, path): 
        '''
        called when the traversal encounters a directory
        processes the directory. 
        Calls process file for .py files in the directory.
        Uses current files's context and relavant documentation to enrich the context. 
        Calls process_dir on subdirectories with the enriched context. 
        '''
        pass


    def parse(self, file)-> List[str]: 
        '''
        parse a .py file using the AST module into a list of strings, each string
        containing the code of a function 
        '''
        pass

    def summarize(self, context, target) -> SummaryResult:
        '''
        @params: 
        target: the function string to be generated 
        Use LLM to summarze the target 
        '''
        pass 

    def run(self) -> None: 
        '''
        runs the whole workflow
        '''
        self.process_dir(self.ROOT) 
        pass