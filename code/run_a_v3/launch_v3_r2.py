from pathlib import Path
import subprocess,shlex
p=Path('/content')
base=['python','/content/chain_a_v3_r1.py','--tracks','/content/tracks_v3.csv','--stations','/content/stations.csv','--observations','/content/observations.csv','--landfalls','/content/landfalls.csv','--land-zip','/content/ne_10m_land.zip','--lead-frozen']
variants=[('main',[]),('hours6',['--hours','6']),('hours18',['--hours','18']),('weight01',['--prior-weight','0.1']),('weight1',['--prior-weight','1']),('bdeck',['--bdeck'])]
cmds=[]
for tag,flags in variants:
    cmd=base+['--output',f'/content/a_v3_r2_{tag}.csv']+flags
    name=f'/content/a_v3_r2_{tag}'
    cmds.append(' '.join(map(shlex.quote,cmd))+f' > {name}.log 2>&1; status=$?; echo $status > {name}.exit; '+('if [ "$status" -ne 0 ]; then touch /content/a_v3_r2.done; exit "$status"; fi' if tag=='main' else 'true'))
(p/'run_v3_r2.sh').write_text('\n'.join(cmds)+'\ntouch /content/a_v3_r2.done\n')
subprocess.Popen(['bash','/content/run_v3_r2.sh'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('launched r2')
