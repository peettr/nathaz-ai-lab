"""Only repair the missing v2 references import path; run frozen v6 segment."""
import runpy,sys
sys.path.insert(0,'/content/v6_work/v6_legacy_code/auto_v2/full_dataset/references')
sys.argv=['/content/v6_work/v6_run_segment.py','--segment','group']
runpy.run_path(sys.argv[0],run_name='__main__')
