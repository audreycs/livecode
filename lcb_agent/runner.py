from typing import List, Dict, Any

from lcb_runner.lm_styles import LMStyle, LanguageModel
from lcb_runner.runner.base_runner import BaseRunner
from .agent import LCBAgent, ProblemContext


class LCBAgentRunner(BaseRunner):
    """
    Runner that integrates LCBAgent with the LiveCodeBench framework
    """
    
    def __init__(self, args, model: LanguageModel):
        super().__init__(args, model)
        
        # Initialize the agent
        self.agent = LCBAgent(
            model_name=args.model,
            max_iterations=getattr(args, 'max_iterations', 5),
            temperature=getattr(args, 'temperature', 0.1),
            timeout=getattr(args, 'timeout', 120),
            workspace_dir=getattr(args, 'workspace_dir', None)
        )
        
    def _run_single(self, prompt: str | list[dict[str, str]]) -> list[str]:
        """
        Run the agent for a single prompt and return the solution
        
        Args:
            prompt: Either a string prompt or a list of message dictionaries
            
        Returns:
            List containing the solution code
        """
        # Convert prompt to string if it's a list of messages
        if isinstance(prompt, list):
            prompt_str = self._extract_prompt_from_messages(prompt)
        else:
            prompt_str = prompt
            
        # Parse the problem from the prompt
        problem = self._parse_problem_from_prompt(prompt_str)
        
        # Solve the problem using the agent
        result = self.agent.solve_problem(problem)
        
        # Return the solution
        return [result['solution']]
    
    def _extract_prompt_from_messages(self, messages: List[Dict[str, str]]) -> str:
        """Extract the problem statement from message format"""
        # Find the user message containing the problem
        for message in messages:
            if message.get('role') == 'user':
                return message.get('content', '')
        
        # Fallback: concatenate all content
        return '\n'.join(msg.get('content', '') for msg in messages if msg.get('content'))
    
    def _parse_problem_from_prompt(self, prompt_str: str) -> ProblemContext:
        """
        Parse the problem statement and test cases from the prompt
        
        This method should be customized based on the LiveCodeBench prompt format
        """
        # Basic parsing - you may need to adjust this based on the actual prompt format
        lines = prompt_str.split('\n')
        
        problem_statement = ""
        examples = []
        constraints = ""
        test_cases = []
        
        current_section = None
        current_example = {}
        
        for line in lines:
            line = line.strip()
            
            if line.lower().startswith('problem'):
                current_section = 'problem'
                continue
            elif line.lower().startswith('example'):
                if current_example:
                    examples.append(current_example)
                current_example = {}
                current_section = 'example'
                continue
            elif line.lower().startswith('constraint'):
                current_section = 'constraints'
                continue
            elif line.lower().startswith('input'):
                if current_section == 'example':
                    current_example['input'] = line.split(':', 1)[1].strip() if ':' in line else ''
                continue
            elif line.lower().startswith('output'):
                if current_section == 'example':
                    current_example['output'] = line.split(':', 1)[1].strip() if ':' in line else ''
                continue
            
            # Add content to current section
            if current_section == 'problem':
                problem_statement += line + '\n'
            elif current_section == 'constraints':
                constraints += line + '\n'
        
        # Add last example if exists
        if current_example:
            examples.append(current_example)
        
        # Convert examples to test cases (basic conversion)
        for example in examples:
            if 'input' in example and 'output' in example:
                test_cases.append({
                    'input': example['input'],
                    'expected': example['output']
                })
        
        # If no test cases from examples, create a basic one
        if not test_cases:
            test_cases = [{'input': '', 'expected': ''}]
        
        return ProblemContext(
            problem_statement=problem_statement.strip(),
            public_test_cases=test_cases,  # Public test cases (examples)
            private_test_cases=None,  # LiveCodeBench doesn't expose private test cases
            constraints=constraints.strip(),
            examples=examples
        )
    
    def cleanup(self):
        """Clean up agent resources"""
        if hasattr(self, 'agent'):
            self.agent.cleanup()


# Factory function to create the runner
def create_lcb_agent_runner(args, model: LanguageModel) -> LCBAgentRunner:
    """Factory function to create LCBAgentRunner"""
    return LCBAgentRunner(args, model)