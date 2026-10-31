import pathlib,os,signal,time
p=int(pathlib.Path('/content/s0_pair_1016.pid').read_text());cmd=pathlib.Path(f'/proc/{p}/cmdline').read_bytes()
assert b'/content/s0_pair_network_1016.py' in cmd,cmd
os.kill(p,signal.SIGTERM);time.sleep(1);print('STOPPED_OLD_WORKER',p,'alive',pathlib.Path(f'/proc/{p}').exists())
