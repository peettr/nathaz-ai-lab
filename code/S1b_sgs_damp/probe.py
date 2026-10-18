from pathlib import Path
for name in ('/content/s1b_driver.log','/content/s1b_case/progress.log','/content/s1b_case/error.txt','/content/s1b_case/short_solver.log','/content/s1b_case/short/RESULTS/feng_coverage.csv','/content/s1b_case/short_delta.txt','/content/s1b_case/all.done'):
 p=Path(name);print(name,p.exists(),p.read_text()[-5000:] if p.exists() else '')
