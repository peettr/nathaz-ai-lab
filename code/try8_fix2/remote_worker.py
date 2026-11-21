import pathlib, runpy, traceback
p=pathlib.Path('/content')
try:
    runpy.run_path('/content/try8_fix2_launch.py',run_name='__main__')
    (p/'try8_fix2_done.marker').write_text('ok\n')
except BaseException:
    traceback.print_exc()
    (p/'try8_fix2_failed.marker').write_text('failed\n')
