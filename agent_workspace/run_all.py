import subprocess, sys
p = subprocess.Popen([sys.executable, 'run_and_capture.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate()
print(out)
if err:
    print('ERR:\n'+err)
