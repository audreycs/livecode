#!/usr/bin/env python3
"""
CLI script to run LiveCodeBench with agent framework.

Usage:
    python agent_runner.py --model gemini-2.5-flash-preview-05-20 --scenario codegeneration --evaluate --release_version release_v1 --n 1

This script provides the same interface as the original runner but uses the
CLI agent framework with tool calling capabilities.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lcb_agent.main import main

if __name__ == "__main__":
    main() 