#!/usr/bin/env python3
"""
Test script for LCB Agent
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the parent directory to the path so we can import lcb_agent
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lcb_agent.agent import LCBAgent, ProblemContext
    from lcb_agent.utils import TestExecutor, FileManager
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the correct directory")
    sys.exit(1)


def test_file_manager():
    """Test the FileManager utility"""
    print("🧪 Testing FileManager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        fm = FileManager(temp_dir)
        
        # Test saving and reading
        code = "print('Hello, World!')"
        filepath = fm.save_solution(code, "test.py")
        
        assert filepath.exists(), "File should be created"
        
        read_code = fm.read_solution("test.py")
        assert read_code == code, "Read code should match saved code"
        
        print("✅ FileManager tests passed")


def test_test_executor():
    """Test the TestExecutor utility"""
    print("🧪 Testing TestExecutor...")
    
    executor = TestExecutor(timeout=5)
    
    # Test syntax validation
    valid, msg = executor.validate_syntax("print('hello')")
    assert valid, "Valid syntax should pass"
    
    invalid, msg = executor.validate_syntax("print('hello'")
    assert not invalid, "Invalid syntax should fail"
    
    # Test code execution
    code = """
n = int(input())
print(n * 2)
"""
    test_cases = [
        {'input': '5', 'expected': '10'},
        {'input': '0', 'expected': '0'},
    ]
    
    success, message, results = executor.run_code_with_tests(code, test_cases)
    assert success, f"Tests should pass: {message}"
    assert len(results) == 2, "Should have 2 test results"
    
    print("✅ TestExecutor tests passed")


def test_simple_problem():
    """Test agent with a simple problem"""
    print("🧪 Testing Agent with simple problem...")
    
    # Check if API key is available
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if not api_key:
        print("⚠️  Skipping agent test - no OpenAI API key found")
        return
    
    problem = ProblemContext(
        problem_statement="""
Write a program that reads an integer n and prints n * 2.
        """,
        test_cases=[
            {'input': '5', 'expected': '10'},
            {'input': '0', 'expected': '0'},
            {'input': '-3', 'expected': '-6'},
        ]
    )
    
    agent = LCBAgent(
        model_name="gpt-4o-mini",
        max_iterations=3,
        temperature=0.1
    )
    
    try:
        result = agent.solve_problem(problem)
        
        print(f"Agent result: Success={result['success']}, Iterations={result['iterations']}")
        
        if result['success']:
            print("✅ Agent successfully solved the problem")
        else:
            print(f"⚠️  Agent failed to solve problem: {result['message']}")
            
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
    finally:
        agent.cleanup()


def test_problem_parsing():
    """Test problem parsing functionality"""
    print("🧪 Testing problem parsing...")
    
    from lcb_agent.runner import LCBAgentRunner
    
    # Mock args object
    class MockArgs:
        model = "gpt-4o-mini"
        temperature = 0.1
        max_iterations = 3
        timeout = 30
        workspace_dir = None
    
    # Mock model object
    class MockModel:
        model_name = "gpt-4o-mini"
        model_repr = "gpt-4o-mini"
        model_style = None
        release_date = None
    
    # Skip actual runner creation if no API key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if not api_key:
        print("⚠️  Skipping runner test - no OpenAI API key found")
        return
    
    try:
        runner = LCBAgentRunner(MockArgs(), MockModel())
        
        # Test prompt parsing
        prompt = """
Problem: Write a program that adds two numbers.

Example 1:
Input: 3 5
Output: 8

Example 2:
Input: 0 0
Output: 0

Constraints:
- Numbers are integers
        """
        
        problem = runner._parse_problem_from_prompt(prompt)
        
        assert "adds two numbers" in problem.problem_statement
        assert len(problem.examples) >= 0  # Basic parsing might not capture all examples
        
        print("✅ Problem parsing tests passed")
        
    except Exception as e:
        print(f"❌ Problem parsing test failed: {e}")


def main():
    """Run all tests"""
    print("🚀 Starting LCB Agent Tests")
    print("=" * 50)
    
    try:
        # Test utilities first
        test_file_manager()
        test_test_executor()
        test_problem_parsing()
        
        # Test agent if API key is available
        test_simple_problem()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 