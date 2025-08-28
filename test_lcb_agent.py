#!/usr/bin/env python3
"""
Test script to run LCB Agent on LiveCodeBench problems
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lcb_agent import LCBAgent, ProblemContext
from lcb_runner.runner.parser import get_args
from lcb_runner.runner.scenario_router import build_prompt_benchmark
from lcb_runner.utils.scenarios import Scenario
from lcb_runner.lm_styles import LMStyle

def extract_examples_from_prompt(prompt_content: str) -> List[Dict[str, str]]:
    """Extract example test cases from LiveCodeBench prompt content"""
    examples = []
    lines = prompt_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for sample input/output sections
        if 'Sample Input' in line or 'Sample Output' in line:
            # Skip the header line
            i += 1
            continue
            
        # Look for input/output pairs in examples
        if line.startswith('Input:') or line.startswith('input:'):
            input_text = line.split(':', 1)[1].strip() if ':' in line else ''
            expected_output = ''
            
            # Look for corresponding output
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith('Output:') or next_line.startswith('output:'):
                    expected_output = next_line.split(':', 1)[1].strip() if ':' in next_line else ''
                    break
                elif next_line.startswith('Input:') or next_line.startswith('input:') or next_line.startswith('Example'):
                    # Found next input or example, stop looking
                    break
                j += 1
            
            if input_text or expected_output:
                examples.append({
                    'input': input_text,
                    'expected': expected_output
                })
            
            i = j  # Skip to after the output line
            continue
            
        # Look for formatted examples like "n = 4, queries = [[0,2],[1,2]]"
        if '=>' in line or '→' in line or 'gives' in line.lower():
            parts = line.split('=>') if '=>' in line else line.split('→') if '→' in line else line.split('gives')
            if len(parts) == 2:
                examples.append({
                    'input': parts[0].strip(),
                    'expected': parts[1].strip()
                })
        
        i += 1
    
    # If no examples found, try to extract from sample sections
    if not examples:
        # Look for sample input/output blocks
        sample_inputs = []
        sample_outputs = []
        
        current_section = None
        for line in lines:
            line = line.strip()
            if 'Sample Input' in line:
                current_section = 'input'
                continue
            elif 'Sample Output' in line:
                current_section = 'output'
                continue
            elif line and current_section == 'input' and not line.startswith('Sample'):
                sample_inputs.append(line)
            elif line and current_section == 'output' and not line.startswith('Sample'):
                sample_outputs.append(line)
        
        # Pair up inputs and outputs
        for i in range(min(len(sample_inputs), len(sample_outputs))):
            examples.append({
                'input': sample_inputs[i],
                'expected': sample_outputs[i]
            })
    
    return examples if examples else [{'input': '', 'expected': ''}]  # Fallback to placeholder

def extract_test_cases_from_problem(problem_data) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Extract both public and private test cases from a CodeGenerationProblem"""
    
    # Extract public test cases
    public_tests = []
    if hasattr(problem_data, 'public_test_cases') and problem_data.public_test_cases:
        for test in problem_data.public_test_cases:
            public_tests.append({
                'input': test.input,
                'expected': test.output
            })
    
    # Extract private test cases  
    private_tests = []
    if hasattr(problem_data, 'private_test_cases') and problem_data.private_test_cases:
        for test in problem_data.private_test_cases:
            private_tests.append({
                'input': test.input,
                'expected': test.output
            })
    
    # Fallback: if no public test cases found, try to extract examples from raw problem content
    if not public_tests and hasattr(problem_data, 'question_content'):
        public_tests = extract_examples_from_prompt(problem_data.question_content)
    
    return public_tests, private_tests

def test_lcb_agent_on_livecode_problems():
    """Test LCB Agent on a few LiveCodeBench problems"""
    print("🧪 Testing LCB Agent on LiveCodeBench problems...")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    # api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if not api_key:
        # Use the hardcoded key from example.py
        api_key = "you_key"
    
    # Create mock args for loading problems
    class MockArgs:
        scenario = Scenario.codegeneration
        release_version = "release_v6"
        not_fast = False
        start_date = None
        end_date = None
        cot_code_execution = False
    
    args = MockArgs()
    
    try:
        # Load some problems from LiveCodeBench
        print("📂 Loading LiveCodeBench problems...")
        benchmark, format_prompt = build_prompt_benchmark(args)
        
        test_problems = benchmark
        print(f"✅ Loaded {len(test_problems)} test problems")
        
        # Create agent
        agent = LCBAgent(
            model_name="gpt-5-mini",  # Use the correct model name
            # model_name="gemini-2.5-flash",
            max_iterations=10,
            temperature=1.0,  # Use default temperature for compatibility
            api_key=api_key
        )
        
        results = []
        
        # Real-time accuracy tracking
        total_evaluated = 0
        total_successful = 0
        
        for i, problem_data in enumerate(test_problems):
            print(f"\n🔄 Testing Problem {i+1}/{len(test_problems)}")
            problem_id = getattr(problem_data, 'question_id', f'problem_{i}')
            print(f"📝 Problem ID: {problem_id}")
            
            try:
                # Extract both public and private test cases from the problem
                public_tests, private_tests = extract_test_cases_from_problem(problem_data)
                
                print(f"📋 Extracted {len(public_tests)} public test case(s)")
                print(f"🔒 Extracted {len(private_tests)} private test case(s)")
                
                # Create problem context directly from raw problem data (NOT pre-formatted prompt)
                problem_context = ProblemContext(
                    problem_statement=problem_data.question_content,  # Use raw content, not formatted prompt
                    public_test_cases=public_tests,  # Used during reflection
                    private_test_cases=private_tests if private_tests else None,  # Used in final evaluation
                    constraints="",  # Could extract from question_content if needed
                    examples=[],  # Agent will create examples from test cases
                    starter_code=getattr(problem_data, 'starter_code', '')  # Pass starter code from dataset
                )
                
                # Solve with agent
                result = agent.solve_problem(problem_context)
                
                # Update accuracy tracking
                total_evaluated += 1
                if result['success']:
                    total_successful += 1
                
                # Calculate and display real-time accuracy
                current_accuracy = (total_successful / total_evaluated) * 100
                
                results.append({
                    "problem_id": problem_id,
                    "success": result['success'],
                    "iterations": result['iterations'],
                    "solution": result['solution']
                })
                
                print(f"✅ Result: {'SUCCESS' if result['success'] else 'FAILED'} "
                      f"(Iterations: {result['iterations']})")
                
                # Print real-time accuracy
                print(f"\n📊 REAL-TIME ACCURACY: {total_successful}/{total_evaluated} = {current_accuracy:.1f}%")
                print(f"🎯 Problems solved successfully: {total_successful}")
                print(f"🔢 Problems evaluated so far: {total_evaluated}")
                
            except Exception as e:
                print(f"❌ Error on problem {i+1}: {e}")
                total_evaluated += 1  # Count failed attempts too
                current_accuracy = (total_successful / total_evaluated) * 100
                
                results.append({
                    "problem_id": problem_id,
                    "success": False,
                    "error": str(e)
                })
                
                # Print real-time accuracy even for errors
                print(f"\n📊 REAL-TIME ACCURACY: {total_successful}/{total_evaluated} = {current_accuracy:.1f}%")
                print(f"🎯 Problems solved successfully: {total_successful}")
                print(f"🔢 Problems evaluated so far: {total_evaluated}")
        
        # Final summary
        final_accuracy = (total_successful / total_evaluated) * 100 if total_evaluated > 0 else 0
        print(f"\n{'='*80}")
        print(f"📊 FINAL SUMMARY")
        print(f"{'='*80}")
        print(f"🎯 Total Problems Solved: {total_successful}")
        print(f"🔢 Total Problems Evaluated: {total_evaluated}")
        print(f"📊 Final Accuracy: {final_accuracy:.1f}%")
        print(f"{'='*80}")
        
        # Save results
        with open("lcb_agent_test_results.json", "w") as f:
            json.dump({
                "summary": {
                    "total_evaluated": total_evaluated,
                    "total_successful": total_successful,
                    "accuracy_percentage": final_accuracy
                },
                "results": results
            }, f, indent=2)
        print(f"💾 Results saved to lcb_agent_test_results.json")
        
        agent.cleanup()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_lcb_agent_on_livecode_problems() 