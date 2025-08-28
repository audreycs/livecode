import subprocess, sys
p = subprocess.Popen(['python3', 'check_solution.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate()
with open('test_output.txt', 'w') as f:
    f.write(out)
    if err:
        f.write('\nERR:\n')
        f.write(err)
print(out)
if err:
    print('ERR:\n'+err)
