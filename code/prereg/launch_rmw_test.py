import subprocess
p = subprocess.Popen(['bash','-lc','cd /content && python -m unittest -v test_rmw_adapter > /content/rmw_test.log 2>&1; echo $? > /content/rmw_test.exit; touch /content/rmw_test.done'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
print('Started RMW-only unit tests on Colab CPU, pid:', p.pid)
