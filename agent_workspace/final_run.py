# Run the tests and print the results
import subprocess
p = subprocess.Popen(['python3', 'check_solution.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate()
print(out)
if err:
    print('ERR:\n'+err)