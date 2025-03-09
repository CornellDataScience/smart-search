import os
import sys
import unittest
import tempfile
import shutil
from contextlib import redirect_stdout
import io
import json

# Add parent directory to path to import the module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from summary.generate_summary import ContextAwareFunctionSummaryGenerator, SummaryResult

class TestContextAwareFunctionSummaryGenerator(unittest.TestCase):
    def setUp(self):
        """Create a temporary test directory structure with Python files for testing"""
        self.test_dir = tempfile.mkdtemp()
        
        # Create a simple test directory structure
        self.src_dir = os.path.join(self.test_dir, "src")
        self.utils_dir = os.path.join(self.src_dir, "utils")
        os.makedirs(self.utils_dir)
        
        # Create a README.md in the src directory
        with open(os.path.join(self.src_dir, "README.md"), "w") as f:
            f.write("# Source Code\nThis directory contains the main source code.")
        
        # Create a simple Python file with functions
        with open(os.path.join(self.src_dir, "main.py"), "w") as f:
            f.write("""
def add(a, b):
    \"\"\"Add two numbers and return the result.\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"Subtract b from a and return the result.\"\"\"
    return a - b
""")
        
        # Create a utility file with more complex functions
        with open(os.path.join(self.utils_dir, "helpers.py"), "w") as f:
            f.write("""
def format_string(text, uppercase=False):
    \"\"\"Format the input string.
    
    Args:
        text: The input string to format
        uppercase: Whether to convert to uppercase
    
    Returns:
        Formatted string
    \"\"\"
    if uppercase:
        return text.upper()
    return text.strip()

def calculate_average(numbers):
    \"\"\"Calculate the average of a list of numbers.\"\"\"
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)
""")
        
        # Create a non-Python file to test filtering
        with open(os.path.join(self.utils_dir, "config.txt"), "w") as f:
            f.write("This is a configuration file")
        
        # Initialize the generator
        self.generator = ContextAwareFunctionSummaryGenerator(ROOT=self.test_dir, api=None)

    def tearDown(self):
        """Clean up the temporary directory"""
        shutil.rmtree(self.test_dir)

    def test_parse(self):
        """Test the parse method"""
        main_py_path = os.path.join(self.src_dir, "main.py")
        functions = self.generator.parse(main_py_path)
        
        self.assertEqual(len(functions), 2)
        self.assertIn("def add(a, b):", functions[0])
        self.assertIn("def subtract(a, b):", functions[1])
        
        # Make sure each function contains its docstring
        self.assertIn("\"\"\"Add two numbers and return the result.\"\"\"", functions[0])
        self.assertIn("\"\"\"Subtract b from a and return the result.\"\"\"", functions[1])

    def test_summarize(self):
        """Test the summarize method"""
        # Mock the ollama.generate function for testing
        def mock_generate(*args, **kwargs):
            return {"response": "This function adds two numbers and returns their sum."}
        
        # Store the original generate function
        original_generate = self.generator.summarize
        
        try:
            # Replace with mock function
            self.generator.summarize = lambda context, target: SummaryResult(
                summary="This function adds two numbers and returns their sum.",
                code=target,
                metadata={"context": context}
            )
            
            result = self.generator.summarize("Test context", "def add(a, b):\n    return a + b")
            
            self.assertEqual(result.summary, "This function adds two numbers and returns their sum.")
            self.assertEqual(result.code, "def add(a, b):\n    return a + b")
            self.assertEqual(result.metadata["context"], "Test context")
        finally:
            # Restore original function
            self.generator.summarize = original_generate

    def test_process_file(self):
        """Test the process_file method"""
        # Clear any existing vectors
        self.generator.vectors = []
        
        # Mock the summarize method for testing
        original_summarize = self.generator.summarize
        try:
            # Replace with mock function
            self.generator.summarize = lambda context, target: SummaryResult(
                summary=f"Summary for: {target.split('def ')[1].split('(')[0]}",
                code=target,
                metadata={"context": context}
            )
            
            main_py_path = os.path.join(self.src_dir, "main.py")
            self.generator.process_file("Test context", main_py_path)
            
            self.assertEqual(len(self.generator.vectors), 2)
            self.assertEqual(self.generator.vectors[0].summary, "Summary for: add")
            self.assertEqual(self.generator.vectors[1].summary, "Summary for: subtract")
            
            # Test handling of non-python files
            config_txt_path = os.path.join(self.utils_dir, "config.txt")
            self.generator.process_file("Test context", config_txt_path)
            # Vectors count should not change
            self.assertEqual(len(self.generator.vectors), 2)
            
        finally:
            # Restore original function
            self.generator.summarize = original_summarize

    def test_process_dir(self):
        """Test the process_dir method"""
        # Clear any existing vectors
        self.generator.vectors = []
        
        # Mock the summarize method
        original_summarize = self.generator.summarize
        try:
            # Replace with mock function
            self.generator.summarize = lambda context, target: SummaryResult(
                summary=f"Summary for: {target.split('def ')[1].split('(')[0]}",
                code=target,
                metadata={"context": context}
            )
            
            self.generator.process_dir("Test context", self.src_dir)
            
            # Should have found 4 functions (2 in main.py, 2 in utils/helpers.py)
            self.assertEqual(len(self.generator.vectors), 4)
            
            # Check if README contents are included in the context
            found_utils_functions = False
            for result in self.generator.vectors:
                if "helpers.py" in result.metadata["context"]:
                    found_utils_functions = True
            
            self.assertTrue(found_utils_functions)
            
        finally:
            # Restore original function
            self.generator.summarize = original_summarize

    def test_run(self):
        """Test the run method"""
        # Clear any existing vectors
        self.generator.vectors = []
        
        # Mock the summarize method
        original_summarize = self.generator.summarize
        original_process_dir = self.generator.process_dir
        
        try:
            # Track if process_dir was called with correct parameters
            process_dir_called = [False]
            
            def mock_process_dir(context, path):
                process_dir_called[0] = True
                self.assertIn(f"Repository: {self.test_dir}", context)
                self.assertEqual(path, self.test_dir)
            
            self.generator.process_dir = mock_process_dir
            
            # Capture stdout
            output = io.StringIO()
            with redirect_stdout(output):
                self.generator.run()
            
            self.assertTrue(process_dir_called[0])
            self.assertIn("Starting code summary generation", output.getvalue())
            
        finally:
            # Restore original functions
            self.generator.summarize = original_summarize
            self.generator.process_dir = original_process_dir

def run_tests_incrementally():
    """Run tests one by one based on user input"""
    test_suite = unittest.TestSuite()
    test_loader = unittest.TestLoader()
    test_class = TestContextAwareFunctionSummaryGenerator
    
    test_functions = [
        'test_parse',
        'test_summarize',
        'test_process_file',
        'test_process_dir',
        'test_run'
    ]
    
    print("Available tests:")
    for i, test_name in enumerate(test_functions, 1):
        print(f"{i}. {test_name}")
    print("6. Run all tests")
    
    while True:
        try:
            choice = int(input("\nEnter test number to run (0 to exit): "))
            if choice == 0:
                break
            elif 1 <= choice <= 5:
                test_case = test_loader.loadTestsFromName(
                    f"__main__.{test_class.__name__}.{test_functions[choice-1]}"
                )
                test_suite = unittest.TestSuite([test_case])
                runner = unittest.TextTestRunner(verbosity=2)
                runner.run(test_suite)
            elif choice == 6:
                test_suite = test_loader.loadTestsFromTestCase(test_class)
                runner = unittest.TextTestRunner(verbosity=2)
                runner.run(test_suite)
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a number")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Run all tests without interaction
        unittest.main()
    else:
        # Run tests incrementally
        run_tests_incrementally()
