import subprocess, sys
p = subprocess.Popen([sys.executable, 'check_solution.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate()
print(out)
print(err)