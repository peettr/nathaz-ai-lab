from pathlib import Path
s=Path('/content/l264a100/texas/pilot.log').read_text(errors='replace').splitlines()
print('LINES',len(s))
for i,line in enumerate(s):
 if any(k in line for k in ['Traceback','RuntimeError','AssertionError','IndexError','CUDA error','device-side assert','ValueError','FileNotFoundError','FORECAST_DONE']):print(i, '\n'.join(s[max(0,i-3):min(len(s),i+6)])[:1500])
