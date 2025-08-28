import os
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import signal

try:
    import openai
    from openai import OpenAI
except ImportError as e:
    raise ImportError("OpenAI library is required. Install with: pip install openai")

from .utils import TestExecutor, FileManager


@dataclass
class ProblemContext:
    """Context for a coding problem"""
    problem_statement: str
    public_test_cases: List[Dict[str, Any]]  # Public test cases (examples) - used during reflection
    private_test_cases: List[Dict[str, Any]] = None  # Private test cases - only for final evaluation
    constraints: str = ""
    examples: List[Dict[str, Any]] = None
    hints: str = ""
    starter_code: str = ""  # Starter code from dataset
    
    @property
    def test_cases(self) -> List[Dict[str, Any]]:
        """For backward compatibility - returns public test cases"""
        return self.public_test_cases


class LCBAgent:
    """
    A self-reflecting agent for LiveCodeBench that uses GPT models
    to iteratively solve coding problems with test-driven development.
    """
    
    def __init__(
        self,
        model_name: str = "gpt-5-mini",
        max_iterations: int = 5,
        workspace_dir: str = None,
        temperature: float = 0.1,
        timeout: int = 120,
        api_key: str = None
    ):
        """
        Initialize the LCB Agent
        
        Args:
            model_name: OpenAI model to use (default: gpt-4o-mini)
            max_iterations: Maximum number of self-reflection iterations
            workspace_dir: Directory for temporary files
            temperature: Model temperature for generation
            timeout: Timeout for code execution
            api_key: OpenAI API key (defaults to environment variable)
        """
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.timeout = timeout
        
        # Initialize tools and managers
        self.file_manager = FileManager()
        self.test_executor = TestExecutor(timeout=30)  # Test-level timeout
        
        # Initialize OpenAI client
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            # Try to get from environment
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
            if not api_key:
                raise ValueError("OpenAI API key must be provided either as parameter or environment variable")
            self.client = OpenAI(api_key=api_key)
        
        # Conversation history for reflection
        self.conversation_history = []
        
        # Define available tools for the agent
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_file",
                    "description": "Create or overwrite a file with the given content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "The name of the file to create (e.g., 'solution.py')"
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to write to the file"
                            }
                        },
                        "required": ["filename", "content"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "read_file",
                    "description": "Read the content of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "The name of the file to read"
                            }
                        },
                        "required": ["filename"]
                    }
                }
            }
        ]
        
    def solve_problem(
        self,
        problem: ProblemContext,
        return_history: bool = False
    ) -> Dict[str, Any]:
        """
        Solve a coding problem using self-reflection loop
        
        During reflection: Uses only public test cases
        Final evaluation: Uses both public and private test cases combined
        
        Args:
            problem: The coding problem context
            return_history: Whether to return the full conversation history
            
        Returns:
            Dictionary containing solution, success status, and metadata
        """
        # Set up overall timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            return self._solve_problem_internal(problem, return_history)
        except TimeoutException:
            print(f"⏰ Agent execution timed out after {self.timeout} seconds")
            return {
                'success': False,
                'solution': "",
                'iterations': 0,
                'message': f"Agent execution timed out after {self.timeout} seconds",
                'test_results': [],
                'public_test_results': [],
                'num_public_tests': len(problem.public_test_cases),
                'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
                'num_total_tests': len(problem.public_test_cases) + (len(problem.private_test_cases) if problem.private_test_cases else 0),
                'history': self.conversation_history if return_history else None
            }
        finally:
            # Reset alarm
            signal.alarm(0)
    
    def _solve_problem_internal(
        self,
        problem: ProblemContext,
        return_history: bool = False
    ) -> Dict[str, Any]:
        """Internal solve method without timeout wrapper"""
        print(f"🚀 Starting to solve problem with {self.model_name}")
        print(f"📝 Problem: {problem.problem_statement[:100]}...")
        
        # Use only public test cases during reflection
        reflection_tests = problem.public_test_cases
        
        # Prepare final test cases (combine public and private)
        final_test_cases = problem.public_test_cases.copy()
        if problem.private_test_cases:
            final_test_cases.extend(problem.private_test_cases)
        
        # Reset conversation history
        self.conversation_history = []

        start_time = time.time()
        
        self._generate_initial_solution(problem)
        iteration = 1
        
        while iteration <= self.max_iterations:
            end_time = time.time()
            if end_time - start_time > 360:
                print(f"⏰ Agent execution timed out after 360 seconds")
                return {
                    'success': False,
                    'solution': "",
                    'iterations': iteration,
                    'message': f"Agent execution timed out after 360 seconds",
                    'test_results': [],
                    'public_test_results': [],
                    'num_public_tests': len(reflection_tests),
                    'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
                    'num_total_tests': len(final_test_cases),
                    'history': self.conversation_history if return_history else None
                }
            
            print(f"\n\n{'='*80}")
            print(f"🔄 ITERATION {iteration}/{self.max_iterations}")
            print(f"{'='*80}")
            
            # Check if solution.py exists and read it
            solution_path = self.file_manager.workspace_dir / "solution.py"
            if not solution_path.exists():
                print("❌ No solution.py file found! Agent must create solution.py using tools.")
                if iteration < self.max_iterations:
                    print("🔄 Asking agent to create solution.py...")
                    self._request_file_creation(problem)
                    iteration += 1
                    continue
                else:
                    print("⏰ Maximum iterations reached without creating solution.py")
                    return {
                        'success': False,
                        'solution': "",
                        'iterations': self.max_iterations,
                        'message': "Agent failed to create solution.py file",
                        'test_results': [],
                        'public_test_results': [],
                        'num_public_tests': len(reflection_tests),
                        'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
                        'num_total_tests': len(final_test_cases),
                        'history': self.conversation_history if return_history else None
                    }
            
            # Read the solution code from the file
            solution_code = self.file_manager.read_solution("solution.py")
            line_count = len(solution_code.splitlines())
            print(f"💾 Found solution.py with {line_count} lines")

            end_time = time.time()
            if end_time - start_time > 360:
                print(f"⏰ Agent execution timed out after 360 seconds")
                return {
                    'success': False,
                    'solution': "",
                    'iterations': iteration,
                    'message': f"Agent execution timed out after 360 seconds",
                    'test_results': [],
                    'public_test_results': [],
                    'num_public_tests': len(reflection_tests),
                    'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
                    'num_total_tests': len(final_test_cases),
                    'history': self.conversation_history if return_history else None
                }
            
            # Run tests on the solution (using public tests during reflection)
            success, message, test_results = self.test_executor.run_code_with_tests(
                solution_code, reflection_tests, has_starter_code=bool(problem.starter_code)
            )
            
            print(f"\n{'='*80}")
            print(f"🧪 TESTING ITERATION {iteration} - PUBLIC TEST RESULTS:")
            print(f"{'='*80}")
            print(f"Overall Result: {message}")
            print(f"{'='*80}")
            
            # Show detailed test results
            for result in test_results:
                status_emoji = "✅" if result['passed'] else "❌"
                print(f"{status_emoji} Test {result['test_id']}:")
                # print(f"   Input: {result['input']}")
                # print(f"   Expected: {result['expected']}")
                # print(f"   Got: {result['output']}")
                # if result['error']:
                #     print(f"   Error: {result['error']}")
                # print()
            print(f"{'='*80}")
            
            if success:
                print("✅ All public tests passed! Running final evaluation...")
                
                # Run final evaluation on combined public + private test cases
                final_success, final_message, final_test_results = self.test_executor.run_code_with_tests(
                    solution_code, final_test_cases, has_starter_code=bool(problem.starter_code)
                )
                
                print(f"\n{'='*80}")
                print(f"🎯 FINAL EVALUATION RESULTS:")
                print(f"{'='*80}")
                print(f"Overall Result: {final_message}")
                print(f"{'='*80}")
                
                if final_test_cases != reflection_tests:
                    # Show summary results for all tests
                    print("Test Results Summary:")
                    for result in final_test_results:
                        status_emoji = "✅" if result['passed'] else "❌"
                        test_type = "(public)" if result['test_id'] < len(reflection_tests) else "(private)"
                        print(f"{status_emoji} Test {result['test_id']} {test_type}: {'PASSED' if result['passed'] else 'FAILED'}")
                    print()
                
                if final_test_cases == reflection_tests:
                    # No private tests, so final results are same as public
                    print(f"(No private tests available)")
                else:
                    print(f"{'='*80}")
                    
                    if not final_success:
                        # Count how many public vs private tests failed
                        public_passed = sum(1 for r in test_results if r['passed'])
                        total_passed = sum(1 for r in final_test_results if r['passed'])
                        private_passed = total_passed - public_passed
                        private_total = len(problem.private_test_cases)
                        
                        print(f"⚠️  Solution passed {public_passed}/{len(reflection_tests)} public tests but only {private_passed}/{private_total} private tests")
                
                print(f"\n{'='*80}")
                print(f"✅ Solution completed in {iteration} iteration(s)")
                print(f"✅ Final result: {final_success}")
                print(f"✅ Passed {len([r for r in final_test_results if r['passed']])}/{len(final_test_cases)} total tests")
                print(f"{'='*80}")
                
                return {
                    'success': final_success,
                    'solution': solution_code,
                    'iterations': iteration,
                    'message': final_message,
                    'test_results': final_test_results,
                    'public_test_results': test_results,
                    'num_public_tests': len(reflection_tests),
                    'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
                    'num_total_tests': len(final_test_cases),
                    'history': self.conversation_history if return_history else None
                }
            
            # If not successful and we haven't reached max iterations, reflect and improve
            if iteration < self.max_iterations:
                print(f"❌ Public tests failed. Reflecting and improving solution...")
                self._reflect_and_improve(
                    problem, solution_code, test_results, message
                )
            
            iteration += 1
        
        print(f"\n{'='*80}")
        print(f"⏰ Maximum iterations ({self.max_iterations}) reached without success.")
        print(f"{'='*80}")
        
        # Even if reflection failed, run final evaluation for complete results
        print("🎯 Running final evaluation on all test cases...")
        final_success, final_message, final_test_results = self.test_executor.run_code_with_tests(
            solution_code, final_test_cases, has_starter_code=bool(problem.starter_code)
        )
        
        print(f"\n{'='*80}")
        print(f"🎯 FINAL EVALUATION RESULTS:")
        print(f"{'='*80}")
        print(f"Overall Result: {final_message}")
        print("Test Results Summary:")
        for result in final_test_results:
            status_emoji = "✅" if result['passed'] else "❌"
            test_type = "(public)" if result['test_id'] <= len(reflection_tests) else "(private)"
            print(f"{status_emoji} Test {result['test_id']} {test_type}: {'PASSED' if result['passed'] else 'FAILED'}")
        print(f"{'='*80}")
        
        print(f"\n{'='*80}")
        print(f"❌ PROBLEM NOT SOLVED")
        print(f"❌ Used all {self.max_iterations} iterations")
        print(f"❌ Final result: {final_success}")
        print(f"❌ Passed {len([r for r in final_test_results if r['passed']])}/{len(final_test_cases)} total tests")
        print(f"{'='*80}")
        
        return {
            'success': False,  # Failed reflection, so overall failure
            'solution': solution_code,
            'iterations': self.max_iterations,
            'message': f"Failed reflection after {self.max_iterations} iterations. Final evaluation: {final_message}",
            'test_results': final_test_results,
            'public_test_results': test_results,
            'num_public_tests': len(reflection_tests),
            'num_private_tests': len(problem.private_test_cases) if problem.private_test_cases else 0,
            'num_total_tests': len(final_test_cases),
            'history': self.conversation_history if return_history else None
        }
    
    def _generate_initial_solution(self, problem: ProblemContext) -> None:
        """Generate the initial solution using tools"""
        prompt = self._create_initial_prompt(problem)
        
        print(f"\n{'='*80}")
        print("🤖 INITIAL PROMPT SENT TO AGENT:")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}")
        
        # Use tools to allow agent to create files
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        self._call_openai_with_tools(messages, "initial_generation")
    
    def _request_file_creation(self, problem: ProblemContext) -> None:
        """Ask agent to create solution.py file"""
        prompt = "You need to create a solution.py file using the create_file tool. Please create the file now."
        
        messages = [
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        self._call_openai_with_tools(messages, "file_creation_request")
    
    def _reflect_and_improve(
        self,
        problem: ProblemContext,
        current_solution: str,
        test_results: List[Dict],
        error_message: str
    ) -> None:
        """Reflect on the current solution and generate an improved version using tools"""
        reflection_prompt = self._create_reflection_prompt(
            problem, current_solution, test_results, error_message
        )
        
        print(f"\n{'='*80}")
        print("🔄 REFLECTION PROMPT SENT TO AGENT:")
        print(f"{'='*80}")
        print(reflection_prompt)
        print(f"{'='*80}")
        
        # Use tools to allow agent to update files
        messages = [
            {
                "role": "user",
                "content": reflection_prompt
            }
        ]
        
        self._call_openai_with_tools(messages, "reflection")
    
    def _create_initial_prompt(self, problem: ProblemContext) -> str:
        """Create the initial prompt for the problem in the specified format"""
        prompt = "=== PROBLEM ===\n\n"
        
        # Extract title from problem statement if possible
        lines = problem.problem_statement.strip().split('\n')
        title = "coding-problem"  # default title
        
        # Try to extract title from first line or look for title-like patterns
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 100 and not first_line.startswith('Write') and not first_line.startswith('Given'):
                title = first_line.lower().replace(' ', '-').replace(':', '').replace(',', '').replace('.', '')
        
        prompt += f"Title: {title}\n\n"
        prompt += f"{problem.problem_statement}\n\n"
        
        if problem.constraints:
            prompt += f"\nConstraints:\n\n{problem.constraints}\n\n"
        
        # Add starter code if available
        if problem.starter_code:
            prompt += f"=== STARTER CODE ===\n\n{problem.starter_code}\n\n"
        
        # Detect if problem has starter code
        has_starter_code = problem.starter_code != ""
        
        prompt += "=== TASK ===\n"
        if has_starter_code:
            prompt += "Complete the Solution class in the starter code to solve the problem.\n"
            prompt += "You must use tools to create a file \"solution.py\" and save your solution class to that file.\n"
            prompt += "Test your solution.py iteratively with a program called check_solution.py, and iterate until it's correct.\n\n"
        else:
            prompt += "You need to solve the problem.\n"
            prompt += "You must use tools to create a file \"solution.py\" which reads from stdin and prints to stdout.\n"
            prompt += "Test your solution.py iteratively with a program called check_solution.py, and iterate until it's correct.\n\n"
        
        prompt += "=== Step guide ===\n"
        prompt += "1. Understand the problem and analyze the examples.\n"
        prompt += "2. Implement your solution in Python.\n"
        prompt += "3. Use the create_file tool to save your solution to 'solution.py'.\n"
        prompt += "4. The solution will be tested automatically with the provided test cases.\n"
        prompt += "5. If tests fail, use tools to read and modify your solution.\n\n"
        
        prompt += "You must use the create_file tool to create solution.py. Do not just return code in your response."
        
        return prompt
    
    def _create_reflection_prompt(
        self,
        problem: ProblemContext,
        current_solution: str,
        test_results: List[Dict],
        error_message: str
    ) -> str:
        """Create a reflection prompt for improving the solution in the specified format"""
        prompt = f"=== PROBLEM ===\n\n"
        prompt += f"{problem.problem_statement}\n\n"
        
        if problem.constraints:
            prompt += f"\nConstraints:\n{problem.constraints}\n\n"
        
        # Add starter code if available
        if problem.starter_code:
            prompt += f"=== STARTER CODE ===\n\n{problem.starter_code}\n\n"
        
        # Detect if problem has starter code for task description
        has_starter_code = problem.starter_code != ""
        
        prompt += "=== TASK ===\n"
        if has_starter_code:
            prompt += "Complete the Solution class in the starter code to solve the problem.\n"
            prompt += "You must use tools to read and update the \"solution.py\" file.\n\n"
        else:
            prompt += "You need to solve the problem.\n"
            prompt += "You must use tools to read and update the \"solution.py\" file which reads from stdin and prints to stdout.\n\n"
        
        prompt += f"=== PREVIOUS TESTING RESULTS ===\n\n"
        prompt += f"Testing on the current solution.py contains errors: {error_message}\n\n"
        
        prompt += "Test failures:\n"
        for result in test_results:
            if not result['passed']:
                prompt += f"\n- Test ID: {result['test_id']}"
                prompt += f"\n- Input:\n{result['input']}"
                prompt += f"\n- Expected:\n{result['expected']}"
                prompt += f"\n- Got:\n{result['output']}"
                if result['error']:
                    prompt += f"\n- Error:\n{result['error']}\n"
                prompt += "\n"
        
        # prompt += f"\n- Your current solution.py -:\n{current_solution}\n"

        prompt += "\nYou should read the current solution.py, analyze the errors, then use the create_file tool to update the solution.py file to pass all test cases. Don't add any debug prints in your code."
        
        return prompt
    
    def _call_openai(self, messages: List[Dict[str, str]], max_retries: int = 3) -> str:
        """Call OpenAI API with retry logic"""
        for attempt in range(max_retries):
            try:
                # Prepare API parameters
                api_params = {
                    "model": self.model_name,
                    "messages": messages,
                    "max_completion_tokens": 4000,
                    "timeout": 120
                }
                
                # Only add temperature if it's not the default (1.0)
                # Some models only support default temperature
                if self.temperature != 1.0:
                    api_params["temperature"] = self.temperature
                
                response = self.client.chat.completions.create(**api_params)
                return response.choices[0].message.content
                
            except Exception as e:
                print(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e
    
    def _call_openai_with_tools(self, messages: List[Dict[str, str]], interaction_type: str, max_retries: int = 3) -> None:
        """Call OpenAI API with tools and handle tool calls"""
        # Keep track of the current conversation
        current_messages = messages.copy()
        
        for attempt in range(max_retries):
            try:
                while True:  # Continue conversation until no more tool calls
                    # Prepare API parameters
                    api_params = {
                        "model": self.model_name,
                        "messages": current_messages,
                        "tools": self.tools,
                        "tool_choice": "auto",
                        "max_completion_tokens": 4000,
                        "timeout": 120
                    }
                    
                    # Only add temperature if it's not the default (1.0)
                    if self.temperature != 1.0:
                        api_params["temperature"] = self.temperature
                    
                    response = self.client.chat.completions.create(**api_params)
                    message = response.choices[0].message
                    
                    print(f"\n🤖 Agent Response:")
                    if message.content:
                        print(f"Content: {message.content}")
                    
                    # Add assistant's response to current messages
                    assistant_message = {"role": "assistant", "content": message.content or ""}
                    if message.tool_calls:
                        assistant_message["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in message.tool_calls
                        ]
                    current_messages.append(assistant_message)
                    
                    # Handle tool calls
                    if message.tool_calls:
                        print(f"🔧 Agent requested {len(message.tool_calls)} tool call(s)")
                        
                        # Execute each tool call and add results to conversation
                        for tool_call in message.tool_calls:
                            result = self._execute_tool_call(tool_call)
                            
                            # Add tool result to conversation
                            tool_message = {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(result) if result is not None else "Tool executed successfully"
                            }
                            current_messages.append(tool_message)
                        
                        # Continue the loop to allow agent to make more tool calls
                        continue
                    else:
                        # No more tool calls, conversation is complete
                        break
                
                # Store in conversation history
                self.conversation_history.append({
                    "type": interaction_type,
                    "messages": messages,
                    "final_response": message.content,
                    "full_conversation": current_messages
                })
                
                return
                
            except Exception as e:
                print(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e
    
    def _execute_tool_call(self, tool_call):
        """Execute a tool call from the agent"""
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        print(f"🔧 Executing tool: {function_name}")
        
        if function_name == "create_file":
            print(f"{arguments['content']}")
            filename = arguments["filename"]
            content = arguments["content"]
            filepath = self.file_manager.save_solution(content, filename)
            print(f"Created file: {filepath}")
            return f"Successfully created file: {filename}"
            
        elif function_name == "read_file":
            print(f"   Arguments: {arguments}")
            filename = arguments["filename"]
            try:
                content = self.file_manager.read_solution(filename)
                print(f"Read file: {filename} ({len(content)} characters)")
                return content
            except FileNotFoundError:
                print(f"❌ File not found: {filename}")
                return f"Error: File {filename} not found"
        
        else:
            print(f"❌ Unknown tool: {function_name}")
            return f"Error: Unknown tool {function_name}"
    
    def cleanup(self):
        """Clean up temporary files"""
        self.file_manager.cleanup()


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Agent execution timed out")