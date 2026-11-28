"""End-to-end synthetic M5 scorer smoke on Colab, isolated from real run."""
from pathlib import Path
import sys
sys.path.insert(0,'/content/m5')
import test_m5_synthetic as fixture
import m5_score as s
root=Path('/content/m5/synthetic_score_v2')
root.mkdir(exist_ok=True)
s.ROOT=root;s.OUT=root/'output';s.OUT.mkdir(exist_ok=True)
fixture.a.to_parquet(root/'train_pairs.parquet',index=False)
fixture.b.to_parquet(root/'test_pairs.parquet',index=False)
original=s.bootstrap
s.bootstrap=lambda frame,fhr,delay:original(frame,fhr,delay,n_draws=3)
s.main()
assert (s.OUT/'swiss_scores_delay4.csv').exists()
assert (s.OUT/'gate.json').exists()
print('SYNTHETIC_MAIN_PASS')
