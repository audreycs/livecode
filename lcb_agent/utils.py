import os
import sys
import subprocess
import tempfile
import traceback
import re
import json
from pathlib import Path
from typing import Tuple, List, Dict, Any
import ast
import signal


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Test execution timed out")


class FileManager:
    """Manages Python file operations for the agent"""
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd() / "agent_workspace"
        self.workspace_dir.mkdir(exist_ok=True)
        
    def save_solution(self, code: str, filename: str = "solution.py") -> Path:
        """Save the solution code to a Python file"""
        filepath = self.workspace_dir / filename
        with open(filepath, 'w') as f:
            f.write(code)
        return filepath
        
    def read_solution(self, filename: str = "solution.py") -> str:
        """Read the solution code from a Python file"""
        filepath = self.workspace_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return f.read()
        return ""
        
    def cleanup(self):
        """Clean up temporary files"""
        for file in self.workspace_dir.glob("*.py"):
            if file.name.startswith("temp_"):
                file.unlink()


class TestExecutor:
    """Executes Python code and runs test cases"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        
    def validate_syntax(self, code: str) -> Tuple[bool, str]:
        """Check if the code has valid Python syntax"""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"
            
    def run_code_with_tests(self, code: str, test_cases: List[Dict[str, Any]], has_starter_code: bool = False) -> Tuple[bool, str, List[Dict]]:
        """
        Run code with test cases and return results
        
        Args:
            code: Python code to execute
            test_cases: List of test cases with 'input' and 'expected' keys
            has_starter_code: Whether this problem has starter code (determines execution method)
            
        Returns:
            Tuple of (success, message, test_results)
        """
        # First validate syntax
        is_valid, error_msg = self.validate_syntax(code)
        if not is_valid:
            # Create failed test results for all test cases when there's a syntax error
            test_results = []
            for i, test_case in enumerate(test_cases):
                test_results.append({
                    'test_id': i,
                    'passed': False,
                    'error': error_msg,
                    'output': None,
                    'expected': test_case.get('expected'),
                    'input': test_case.get('input')
                })
            return False, error_msg, test_results
            
        test_results = []
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
            
        try:
            for i, test_case in enumerate(test_cases):
                result = self._run_single_test(temp_file, test_case, i, has_starter_code)
                test_results.append(result)
                
            # Check if all tests passed
            passed_tests = sum(1 for r in test_results if r['passed'])
            total_tests = len(test_results)
            
            if passed_tests == total_tests:
                return True, f"All {total_tests} tests passed!", test_results
            else:
                return False, f"Only {passed_tests}/{total_tests} tests passed", test_results
                
        finally:
            # Clean up temporary file
            os.unlink(temp_file)
            
    def _run_single_test(self, code_file: str, test_case: Dict[str, Any], test_id: int, has_starter_code: bool) -> Dict:
        """Run a single test case"""
        result = {
            'test_id': test_id,
            'passed': False,
            'error': None,
            'output': None,
            'expected': test_case.get('expected'),
            'input': test_case.get('input')
        }
        
        try:
            # Check if this is a starter code problem with Solution class
            with open(code_file, 'r') as f:
                code_content = f.read()
            
            if has_starter_code:
                print(f"Running class-based test for test case!")
                # Handle starter code solution using dynamic import
                result = self._run_class_based_test(code_file, test_case, test_id)
            else:
                print(f"Running script-based test for test case!")
                # Handle standard input/output solution using subprocess
                result = self._run_script_based_test(code_file, test_case, test_id)
                
        except Exception as e:
            result['error'] = f"Test execution error: {str(e)}"
            
        return result
    
    def _run_class_based_test(self, code_file: str, test_case: Dict[str, Any], test_id: int) -> Dict:
        """Run test for class-based solution using dynamic import"""
        import importlib.util
        import sys as _sys
        import json
        
        result = {
            'test_id': test_id,
            'passed': False,
            'error': None,
            'output': None,
            'expected': test_case.get('expected'),
            'input': test_case.get('input')
        }
        
        # Set up timeout signal
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            # Import solution module from code file
            spec = importlib.util.spec_from_file_location("solution", code_file)
            solution_module = importlib.util.module_from_spec(spec)
            _sys.modules["solution"] = solution_module
            spec.loader.exec_module(solution_module)
            
            # Find the Solution class
            if not hasattr(solution_module, 'Solution'):
                result['error'] = "No Solution class found in solution.py"
                return result
            
            # Create instance of Solution class
            solution_instance = solution_module.Solution()
            
            # Find the main method (first public method)
            methods = [method for method in dir(solution_instance) if not method.startswith('_')]
            if not methods:
                result['error'] = "No public methods found in Solution class"
                return result
            
            method_name = methods[0]
            method = getattr(solution_instance, method_name)
            
            # Parse the input data
            parsed_input = self._parse_test_input(test_case.get('input'))
            
            # Call the method with appropriate arguments
            try:
                if isinstance(parsed_input, list) and len(parsed_input) > 1:
                    # Multiple arguments - unpack the list
                    method_result = method(*parsed_input)
                else:
                    # Single argument - pass the parsed input directly
                    # This preserves lists as lists and scalars as scalars
                    method_result = method(parsed_input)
            except TypeError as e:
                # If the method signature doesn't match, try different approaches
                if "takes" in str(e) and "arguments" in str(e):
                    if isinstance(parsed_input, list):
                        method_result = method(parsed_input)
                    else:
                        method_result = method(parsed_input)
                else:
                    print(f"Input: {parsed_input}, Error: {e}")
                    raise e
            
            # Handle tuple vs list conversion for comparison
            if isinstance(method_result, tuple):
                method_result = list(method_result)
            
            result['output'] = str(method_result)
            
            # Parse expected output
            expected = test_case.get('expected')
            if isinstance(expected, str):
                try:
                    expected_obj = json.loads(expected)
                except json.JSONDecodeError:
                    expected_obj = expected
            else:
                expected_obj = expected
            
            # Direct Python object comparison
            result['passed'] = (method_result == expected_obj)
            
            if not result['passed']:
                result['error'] = f"Expected: {expected_obj}, Got: {method_result}"
                
        except TimeoutException:
            result['error'] = f"Test timed out after {self.timeout} seconds"
        except Exception as e:
            result['error'] = f"Test execution error: {str(e)}"
        finally:
            # Reset alarm
            signal.alarm(0)
            
        return result
    
    def _run_script_based_test(self, code_file: str, test_case: Dict[str, Any], test_id: int) -> Dict:
        """Run test for script-based solution using subprocess (original method)"""
        result = {
            'test_id': test_id,
            'passed': False,
            'error': None,
            'output': None,
            'expected': test_case.get('expected'),
            'input': test_case.get('input')
        }
        
        try:
            # Prepare the test input
            test_input = test_case.get('input', '')
            if isinstance(test_input, list):
                test_input = '\n'.join(map(str, test_input))
            elif not isinstance(test_input, str):
                test_input = str(test_input)
                
            # Run the code with test input
            process = subprocess.run(
                [sys.executable, code_file],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if process.returncode == 0:
                output = process.stdout.strip()
                expected = str(test_case.get('expected', '')).strip()
                
                result['output'] = output
                
                # Try multiple comparison strategies
                result['passed'] = self._compare_outputs(output, expected)
                
                if not result['passed']:
                    result['error'] = f"Expected: {expected}, Got: {output}"
            else:
                result['error'] = f"Runtime error: {process.stderr}"
                
        except subprocess.TimeoutExpired:
            result['error'] = f"Test timed out after {self.timeout} seconds"
        except Exception as e:
            result['error'] = f"Execution error: {str(e)}"
            
        return result
    
    def _parse_test_input(self, test_input):
        """Parse test input into appropriate Python objects"""
        import json
        
        if test_input is None:
            return None
            
        # If it's already a Python object, return as-is
        if not isinstance(test_input, str):
            return test_input
        
        # Handle multi-line inputs (split by newlines)
        if '\n' in test_input.strip():
            lines = [line.strip() for line in test_input.strip().split('\n') if line.strip()]
            parsed_args = []
            
            for line in lines:
                # Try to parse each line as JSON first
                try:
                    parsed_args.append(json.loads(line))
                except json.JSONDecodeError:
                    # Try to evaluate as Python literal
                    try:
                        parsed_args.append(eval(line))
                    except:
                        # Keep as string if parsing fails
                        parsed_args.append(line)
            
            return parsed_args
        
        # Single line input - try to parse as JSON first
        try:
            return json.loads(test_input)
        except json.JSONDecodeError:
            pass
            
        # Try to evaluate as Python literal
        try:
            return eval(test_input)
        except:
            pass
            
        # Return as string if all else fails
        return test_input
        
    def _compare_outputs(self, actual: str, expected: str) -> bool:
        """
        Compare outputs with robust strategies to handle debug prints
        """
        # Strategy 1: Exact match (original behavior)
        if actual == expected:
            return True
            
        # Strategy 2: Extract result after "Got:" if present
        if "Got:" in actual:
            # Find the text after "Got:" and extract the result
            got_match = re.search(r'Got:\s*(.+?)(?:\n|$)', actual)
            if got_match:
                got_result = got_match.group(1).strip()
                if got_result == expected:
                    return True
        
        return False
        
    def extract_function_from_code(self, code: str, function_name: str = None) -> str:
        """Extract a specific function from code or return the whole code"""
        if function_name is None:
            return code
            
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    return ast.unparse(node)
        except:
            pass
            
        return code 