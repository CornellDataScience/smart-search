from typing import Dict, List, Optional
from pydantic import BaseModel
import ollama
import os
import ast
import re

class FileRelationship(BaseModel):
    uses: str
    description: str

class UsedByRelationship(BaseModel):
    used_by: str
    description: str

class FileContext(BaseModel):
    uses_relationships: List[FileRelationship]
    used_by_relationships: List[UsedByRelationship]

class RelationalContext:
    def _build_codebase_index(self) -> None:
        """Build an index of all files and packages in the codebase"""
        for root, dirs, files in os.walk(self.base_path):
            # Add Python files to codebase_files
            for file in files:
                if file.endswith('.py'):
                    # Convert to relative path from base_path
                    rel_path = os.path.relpath(os.path.join(root, file), self.base_path)
                    # Convert to import-style path
                    import_path = rel_path.replace('/', '.').replace('\\', '.')[:-3]  # Remove .py
                    self.codebase_files.add(import_path)
            
            # Check for packages (directories with __init__.py)
            if '__init__.py' in files:
                # Convert to relative path from base_path
                rel_path = os.path.relpath(root, self.base_path)
                # Convert to import-style path
                import_path = rel_path.replace('/', '.').replace('\\', '.')
                self.codebase_packages.add(import_path)

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.relationships: Dict[str, FileContext] = {}
        self.codebase_files = set()  # Set of all files in the codebase
        self.codebase_packages = set()  # Set of all packages in the codebase
        self._build_codebase_index()  # Build the index on initialization
        self.relationship_prompt = """
        Analyze the following Python code and identify how it uses other files in the codebase.
        For each imported file, describe SPECIFICALLY how the imported components are used in the code.
        Look for:
        1. What classes/functions are imported
        2. How these imports are used in the code (specific methods called, inheritance, etc.)
        3. The purpose of using these imports in the context of this file
        
        Format your response in this EXACT format:
        target_file|Imports [component] for [specific usage details], [another usage], and [another usage]
        
        Example:
        validator.py|Imports DataValidator for validating user input data, enforcing data type constraints, and checking required fields
        
        DO NOT mention generic terms like "use in the code". Instead, describe the specific purposes and functionalities.
        Description should be clear and concise. Should be a single sentence yet descriptive
        
        Here's the code to analyze:
        """

    def _is_local_import(self, import_path: str) -> bool:
        """Check if an import is from our local codebase"""
        return import_path in self.codebase_files or import_path in self.codebase_packages

    def _extract_imports(self, file_content: str) -> List[str]:
        """Extract all import statements from a file and identify local imports"""
        try:
            tree = ast.parse(file_content)
            local_imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if self._is_local_import(name.name):
                            local_imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and self._is_local_import(node.module):
                        local_imports.append(node.module)
            
            return local_imports
        except Exception as e:
            print(f"Error parsing imports: {e}")
            return []

    def _analyze_file_relationships(self, file_path: str, file_content: str) -> List[FileRelationship]:
        """Analyze a file's content to infer its relationships with other files"""
        try:
            # First get local imports
            local_imports = self._extract_imports(file_content)
            
            # Then use LLM to infer relationships
            response = ollama.generate(
                model="llama3.2:latest",
                prompt=self.relationship_prompt + file_content,
                stream=False,
                options={
                    'num_predict': -1,
                    'keep_alive': 0,
                    'temperature': 0.2  # Lower temperature for more focused responses
                },
            )
            
            relationships = []
            seen_targets = set()  # Track seen targets to avoid duplicates
            
            # Parse LLM response
            for line in response['response'].strip().split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue
                    
                try:
                    target, desc = line.split('|', 1)
                    target = target.strip()
                    desc = desc.strip()
                    
                    # Skip if we've already processed this target
                    if target in seen_targets:
                        continue
                        
                    # Only add if it's a local file and description is meaningful
                    if (self._is_local_import(target) and 
                        len(desc) > 20 and  # Ensure description is substantial
                        "use in the code" not in desc.lower()):  # Avoid generic descriptions
                        relationship = FileRelationship(
                            uses=target,
                            description=desc
                        )
                        relationships.append(relationship)
                        seen_targets.add(target)
                except (ValueError, IndexError) as e:
                    print(f"Warning: Skipping malformed relationship line: {line}")
                    continue
            
            # For any remaining imports that weren't described by the LLM
            for imp in local_imports:
                if imp not in seen_targets:
                    # Get a more detailed description for this import
                    detail_prompt = f"""
                    Analyze this specific import '{imp}' in the following code and describe 
                    SPECIFICALLY how it is used. Focus on actual functionality, methods called,
                    and purpose in the code. DO NOT use generic descriptions.
                    Description should be clear and concise. Should be a single sentence yet descriptive
                    
                    {file_content}
                    """
                    
                    detail_response = ollama.generate(
                        model="llama3.2:latest",
                        prompt=detail_prompt,
                        stream=False,
                        options={
                            'num_predict': -1,
                            'keep_alive': 0,
                            'temperature': 0.2
                        },
                    )
                    
                    description = detail_response['response'].strip()
                    if len(description) > 20:  # Ensure description is substantial
                        relationship = FileRelationship(
                            uses=imp,
                            description=f"Imports {imp} for {description}"
                        )
                        relationships.append(relationship)
            
            return relationships
        except Exception as e:
            print(f"Error analyzing relationships for {file_path}: {e}")
            return []

    def _build_used_by_relationships(self):
        """Build the used_by relationships for each file based on the uses relationships"""
        # Initialize used_by lists for all files
        for file_path in self.relationships:
            if not isinstance(self.relationships[file_path], FileContext):
                self.relationships[file_path] = FileContext(
                    uses_relationships=self.relationships[file_path],
                    used_by_relationships=[]
                )

        # Build used_by relationships
        for source_file, context in self.relationships.items():
            for relationship in context.uses_relationships:
                target_file = relationship.uses
                # Convert to full path if needed
                if not target_file.endswith('.py'):
                    target_file = f"{target_file}.py"
                if not target_file.startswith('testrelation/'):
                    target_file = f"testrelation/{target_file}"
                
                # Add used_by relationship to the target file
                if target_file in self.relationships:
                    # Rephrase description from target's perspective
                    original_desc = relationship.description.lower()
                    
                    # Remove common import prefixes if they exist
                    desc = original_desc
                    for prefix in ["imports", "uses", "utilizes"]:
                        if desc.startswith(prefix.lower()):
                            desc = desc[len(prefix):].strip()
                            if desc.startswith("for"):
                                desc = desc[3:].strip()
                    
                    # Extract the component name if mentioned
                    component = ""
                    if target_file.replace(".py", "") in desc:
                        parts = desc.split(target_file.replace(".py", ""))
                        if len(parts) > 1:
                            desc = parts[1].strip()
                    
                    # Create the new description
                    source_name = os.path.basename(source_file).replace(".py", "")
                    new_desc = f"{source_name} expects {desc}"
                    
                    used_by = UsedByRelationship(
                        used_by=source_file,
                        description=new_desc
                    )
                    self.relationships[target_file].used_by_relationships.append(used_by)

    def process_file(self, file_path: str) -> None:
        """Process a single file and store its relationships"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            relationships = self._analyze_file_relationships(file_path, content)
            self.relationships[file_path] = FileContext(
                uses_relationships=relationships,
                used_by_relationships=[]
            )
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    def process_directory(self, directory: str) -> None:
        """Process all Python files in a directory recursively"""
        # First build/update the codebase index
        self._build_codebase_index()
        
        # Then process all files
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    self.process_file(full_path)
        
        # After processing all files, build the used_by relationships
        self._build_used_by_relationships()

    def save_to_json(self, output_file: str) -> None:
        """Save relationships to a JSON file"""
        import json
        with open(output_file, 'w') as f:
            json.dump(
                {k: v.model_dump() for k, v in self.relationships.items()},
                f,
                indent=2
            )

    def load_from_json(self, input_file: str) -> None:
        """Load relationships from a JSON file"""
        import json
        with open(input_file, 'r') as f:
            data = json.load(f)
            self.relationships = {
                k: FileContext(**v)
                for k, v in data.items()
            }

def main():
    # Example usage
    base_path = "testrelation"  # Your codebase path
    context = RelationalContext(base_path)
    context.process_directory(base_path)
    context.save_to_json("relationships.json")

if __name__ == "__main__":
    main()
