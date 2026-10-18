from pathlib import Path
s=Path('/content/Strata/setup.py').read_text().splitlines()
for a,b in [(3570,3640),(3998,4026),(6050,6070),(6088,6105)]:
 print('SECTION',a,b)
 print('\n'.join(f'{i+1}: {s[i]}' for i in range(a-1,b)))
