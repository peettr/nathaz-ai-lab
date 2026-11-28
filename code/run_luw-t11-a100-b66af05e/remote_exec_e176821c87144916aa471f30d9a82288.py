import sys; sys.path.insert(0,'/content')
import remote_io as io
print('ACK_OK', (io.C/'t11/out/E_s102_off.ack.json').is_file(), flush=True)
