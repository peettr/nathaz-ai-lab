import json,pathlib
p=json.loads(pathlib.Path('/content/s0_pair_1016/progress.json').read_text());print(p['paired'][0])
