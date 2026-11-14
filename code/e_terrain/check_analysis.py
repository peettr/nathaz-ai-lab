import os,glob
p='/content/e_terrain/analysis.log'
print('ALIVE',os.path.exists('/proc/'+open('/content/e_terrain/analysis_pid').read().strip()))
print('LOG','\n'.join(open(p).read().splitlines()[-15:]))
print('OUTPUTS',glob.glob('/content/e_terrain/analysis_v1/*'))
