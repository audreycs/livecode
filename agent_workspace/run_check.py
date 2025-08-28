import subprocess, sys
p = subprocess.Popen([sys.executable, 'check_solution.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate()
print(out.decode())
print(err.decode())
