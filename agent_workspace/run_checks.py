import subprocess, sys

print('Running check_solution.py')
res = subprocess.run([sys.executable, 'check_solution.py'], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
