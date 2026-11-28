from pathlib import Path
import subprocess, sys, traceback
root=Path('/content/l2631')
try:
    result=subprocess.run([sys.executable,'-u',str(root/'train_a0_resume_v2.py'),
                           '--root',str(root/'weatherbench'),
                           '--out',str(root/'output'),
                           '--epochs','60','--batch','64'],check=False)
    (root/'train_v2.exitcode').write_text(str(result.returncode))
    if result.returncode==0:
        assert (root/'output/all.done').exists()
        (root/'train_v2.done').write_text('all seeds evaluated and Drive checkpoints verified\n')
    else:
        (root/'train_v2.failed').write_text(str(result.returncode))
except BaseException:
    (root/'train_v2.failed').write_text(traceback.format_exc())
    raise
