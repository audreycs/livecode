import subprocess, sys
with open('manual_test_input.txt') as f:
    inp = f.read()
p = subprocess.Popen([sys.executable, 'solution.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate(inp)
print('OUT:\n' + out)
print('ERR:\n' + err)