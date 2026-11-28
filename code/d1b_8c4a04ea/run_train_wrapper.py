from pathlib import Path
import subprocess, sys, traceback
root=Path('/content/l2631')
try:
    result=subprocess.run([sys.executable,'-u',str(root/'train_a0_earlystop.py'),
                           '--root',str(root/'weatherbench'),
                           '--out',str(root/'output'),
                           '--epochs','60','--batch','64'],check=False)
    (root/'train.exitcode').write_text(str(result.returncode))
    if result.returncode==0:
        assert (root/'output/all.done').exists()
        (root/'train.done').write_text('all seeds evaluated and checkpoints copied to Drive\n')
    else:
        (root/'train.failed').write_text(str(result.returncode))
except BaseException:
    (root/'train.failed').write_text(traceback.format_exc())
    raise
