import sys;sys.path.insert(0,'/content')
import remote_io_full as io
print('ACK_PRESENT', (io.C/'t15/out/WM_s108.ack.json').is_file(),flush=True)
