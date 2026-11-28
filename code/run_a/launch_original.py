from pathlib import Path
import subprocess
Path('/content/a_original.launch').open('x').write('original frozen implementation launched once\n')
cmd=['python','/content/chain_a_v2.py','--tracks','/content/a_inputs_v2/tracks.csv','--stations','/content/a_inputs_v2/stations.csv','--observations','/content/a_inputs_v2/observations.csv','--landfalls','/content/a_inputs_v2/landfalls.csv','--land-zip','/content/ne_10m_land.zip','--output','/content/a_original_rows.csv','--lead-frozen']
cmd2=' '.join(cmd)+' > /content/a_original.log 2>&1; echo $? > /content/a_original.exit; touch /content/a_original.done'
p=subprocess.Popen(['bash','-lc',cmd2],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('frozen_pid',p.pid)
