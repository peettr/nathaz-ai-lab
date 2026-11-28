import sys; sys.path.insert(0,'/content')
import remote_io as io
print('PROBE '+io.json.dumps(io.probe(io.C)),flush=True)
