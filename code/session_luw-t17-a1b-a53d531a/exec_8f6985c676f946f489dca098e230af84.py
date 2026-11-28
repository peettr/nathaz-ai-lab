import sys;sys.path.insert(0,'/content')
import remote_diag as io
print('DIAG_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)
