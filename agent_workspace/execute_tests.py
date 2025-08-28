import subprocess, sys
p = subprocess.Popen([sys.executable, '__run_check.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate()
print(out)
if err:
    print('ERR:\n'+err)
