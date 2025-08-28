# LCB Agent Framework

A self-reflecting agent framework for LiveCodeBench that uses GPT models to iteratively solve coding problems with test-driven development.

## Features

- **Self-Reflection Loop**: The agent tests its solutions and iteratively improves them
- **GPT Model Integration**: Uses OpenAI's GPT models (default: GPT-4o-mini)
- **Test-Driven Development**: Automatically runs test cases and reflects on failures
- **File Management**: Saves solutions to Python files for debugging
- **LiveCodeBench Integration**: Seamless integration with the existing LiveCodeBench framework

## Architecture

```
LCBAgent
├── agent.py          # Main agent class with self-reflection loop
├── runner.py          # Integration with LiveCodeBench framework
├── utils.py           # Utility classes for file management and test execution
├── example.py         # Example usage demonstrations
└── __init__.py        # Package initialization
```

## Usage

### Basic Usage

```python
from lcb_agent import LCBAgent, ProblemContext

# Define a problem
problem = ProblemContext(
    problem_statement="Write a function to compute factorial of n",
    public_test_cases=[  # Public test cases used during reflection
        {'input': '5', 'expected': '120'},
        {'input': '0', 'expected': '1'},
    ],
    private_test_cases=[  # Optional: Private test cases for final evaluation
        {'input': '3', 'expected': '6'},
        {'input': '1', 'expected': '1'},
    ]
)

# Create agent
agent = LCBAgent(
    model_name="gpt-4o-mini",
    max_iterations=5,
    temperature=0.1
)

# Solve the problem (automatic two-phase testing)
result = agent.solve_problem(problem)

# Or solve with final evaluation on private test cases
result = agent.solve_problem(problem, use_private_tests_for_final=True)

print(f"Success: {result['success']}")
print(f"Solution:\n{result['solution']}")

# Cleanup
agent.cleanup()
```

### Integration with LiveCodeBench

```python
from lcb_agent.runner import LCBAgentRunner
from lcb_runner.lm_styles import LanguageModel, LMStyle

# Create model configuration
model = LanguageModel(
    model_name="gpt-4o-mini",
    model_repr="gpt-4o-mini",
    model_style=LMStyle.OpenAIChat,
    release_date=None
)

# Create runner
runner = LCBAgentRunner(args, model)

# Use runner in LiveCodeBench pipeline
result = runner._run_single(prompt)
```

## Configuration

### Agent Parameters

- **model_name**: OpenAI model to use (default: "gpt-4o-mini")
- **max_iterations**: Maximum number of self-reflection iterations (default: 5)
- **temperature**: Model temperature for generation (default: 0.1)
- **timeout**: Timeout for code execution in seconds (default: 30)
- **workspace_dir**: Directory for temporary files (default: auto-generated)

### Environment Variables

- **OPENAI_API_KEY** or **OPENAI_KEY**: Your OpenAI API key (required)

## Workflow

1. **Initial Generation**: Agent generates first solution attempt
2. **Test Execution**: Solution is saved to file and tested with provided test cases
3. **Self-Reflection**: If tests fail, agent analyzes failures and generates improved solution
4. **Iteration**: Process repeats until all tests pass or max iterations reached
5. **Result**: Returns final solution with success status and metadata

## Example Output

```
🚀 Starting to solve problem with gpt-4o-mini
📝 Problem: Write a function to compute factorial of n...

🔄 Iteration 1/5
💾 Saved solution to agent_workspace/solution_iter_1.py
🧪 Test Results: Only 2/3 tests passed

❌ Tests failed. Reflecting and improving solution...

🔄 Iteration 2/5
💾 Saved solution to agent_workspace/solution_iter_2.py
🧪 Test Results: All 3 tests passed!

✅ All tests passed! Problem solved successfully.
```

## Running Examples

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Run examples
cd lcb_agent
python example.py
```

## Dependencies

- `openai`: OpenAI Python library
- `ast`: Python AST parsing (built-in)
- `subprocess`: Process execution (built-in)
- `pathlib`: Path handling (built-in)

Install OpenAI library:
```bash
pip install openai
```

## Error Handling

The agent includes robust error handling for:
- OpenAI API failures with retry logic
- Syntax errors in generated code
- Runtime errors during test execution
- Timeout errors for long-running code
- File system operations

## Customization

### Custom Problem Parsing

Extend the `_parse_problem_from_prompt` method in `runner.py` to handle different prompt formats:

```python
def _parse_problem_from_prompt(self, prompt_str: str) -> ProblemContext:
    # Custom parsing logic for your prompt format
    pass
```

### Custom Test Cases

Create test cases with different input/output formats:

```python
test_cases = [
    {
        'input': ['5', '3'],  # Multiple inputs
        'expected': '8'
    },
    {
        'input': 'complex input format',
        'expected': 'expected output'
    }
]
```

## Limitations

- Currently supports Python code generation only
- Requires OpenAI API access
- Test cases must be deterministic
- Limited to text-based input/output

## Contributing

To extend the framework:
  1. Add new model integrations in `agent.py`
  2. Enhance prompt parsing in `runner.py`
  3. Add new test execution strategies in `utils.py`
  4. Create additional examples in `example.py`

## Test Case Management

The agent uses a **two-phase testing approach**:

### **Phase 1: Reflection (Public Test Cases Only)**
- Uses **only public test cases** during the self-reflection loop
- Agent can see these results and use them to improve solutions
- Typically examples from the problem statement
- Should be representative but not comprehensive

### **Phase 2: Final Evaluation (Public + Private Test Cases)**
- **Automatically combines both public and private test cases**
- Tests the final solution against the complete test suite
- Provides detailed breakdown of public vs private test performance
- Detects overfitting to public examples

### **Example Usage**

```python
problem = ProblemContext(
    problem_statement="Find the sum of two numbers",
    public_test_cases=[  # Used during reflection
        {'input': '2 3', 'expected': '5'},
        {'input': '0 0', 'expected': '0'},
    ],
    private_test_cases=[  # Combined with public for final evaluation
        {'input': '10 20', 'expected': '30'},
        {'input': '-5 7', 'expected': '2'},
        {'input': '100 200', 'expected': '300'},
    ]
)

# Solve the problem (automatic two-phase testing)
result = agent.solve_problem(problem)

# Check results
print(f"Final success: {result['success']}")
print(f"Public tests passed: {sum(1 for r in result['public_test_results'] if r['passed'])}/{result['num_public_tests']}")
print(f"Total tests passed: {sum(1 for r in result['test_results'] if r['passed'])}/{result['num_total_tests']}")
print(f"Private tests: {result['num_private_tests']}")
```

### **Benefits**
- **Prevents overfitting**: Agent can't see private test results during development
- **Comprehensive evaluation**: Final solution tested against complete test suite  
- **Better guidance**: Public tests guide reflection without revealing all requirements
- **Detailed feedback**: Clear breakdown of public vs private performance