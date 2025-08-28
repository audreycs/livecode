import subprocess, sys

print(subprocess.run([sys.executable, 'check_solution.py'], capture_output=False).stdout)