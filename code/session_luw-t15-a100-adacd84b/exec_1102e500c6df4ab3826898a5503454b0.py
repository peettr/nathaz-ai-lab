import sys;sys.path.insert(0,'/content')
import remote_io_full as io
print('T15_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)
