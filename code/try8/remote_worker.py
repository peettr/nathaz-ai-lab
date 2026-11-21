import pathlib, runpy, traceback
p=pathlib.Path('/content')
try:
    runpy.run_path('/content/try8_launch.py',run_name='__main__')
    (p/'try8_done.marker').write_text('ok\n')
except BaseException:
    traceback.print_exc()
    (p/'try8_failed.marker').write_text('failed\n')
