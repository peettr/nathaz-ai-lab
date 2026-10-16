#!/usr/bin/env python3
import json,hashlib
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
translations=[
'Which study quantified downburst wind fields in the WindEEE Dome?',
'Which research generated full-scale downburst speeds using an observation-driven simulation method?',
'Which paper combined physical and numerical models of thunderstorm downdrafts?',
'Which study improved engineering downburst outflow simulation with a cooling-source approach?',
'Which numerical investigation tested how terrain modifies downburst winds?',
'Which impinging-jet numerical study compared stationary and moving downburst storms?',
'Which experiment reproduced evolving downburst-like flows with an actively controlled multi-blade device?',
'Which research compared impinging-jet and cooling-source representations of microbursts?',
'Which parametric study examined near-ground outflow from a line-shaped downburst?',
'Which paper assessed microburst models for predicting downdrafts?',
'Which work proposed a simple axisymmetric analytical microburst downdraft model?',
'Which paper used large-eddy simulation to study peak high-rise wind loading in an atmospheric boundary layer?',
'Which study evaluated LES as a high-rise wind-load design method?',
'Which work studied extreme pressures on a high-rise roof with validated simulations and experiments?',
'Which CFD setup benchmark for tall-building wind loads used the CAARC building?',
'Which paper modeled low-rise building pressures using translation processes?',
'Which study used Gaussian process regression to interpolate building pressures?',
'Which paper assessed a modified random-flow-generation method for unsteady building pressures?',
'Which work investigated sampling and moment-based translation biases in non-Gaussian extreme wind pressures?',
'Which study developed analysis of pressure-tap data for low-rise cladding and components?',
'Which paper compared local wall pressures of low-rise buildings with US and Japanese provisions?',
'Which LES study defined spectral and coherence properties of hurricane boundary layer winds?',
'Which paper formulated a theoretical wind response spectrum?',
'Which work revisited the gustiness spectrum in strong winds and the von Karman formula?',
'Which study simulated nonhomogeneous fluctuating wind fields with an evolutionary wavenumber-frequency spectrum?',
'Which paper developed a general inlet turbulence generator for large-eddy simulation?',
'Which study compared three neutral-boundary-layer LES inlet methods across rough terrain?',
'Which new turbulence generator was evaluated on standard high-rise building LES wind effects?',
'Which work benchmarked LES for wind loads and structural response of a low-rise building?',
'Which study used CFD surrogate models to evaluate aeroelastic effects of changing streamlined bridge cross-sections?',
'Which review discussed practical CFD determination of wind loads on high-rise buildings?',
'Which work used adaptive Kriging to optimize uncertain tall buildings for occupant comfort?',
'Which classic numerical study investigated dynamics and structure of an isolated microburst?',
'Which study compared measurements and numerical simulations of an impinging jet representing thunderstorm microburst winds?']
a=[json.loads(s) for s in (R/'questions.jsonl').open()]
assert len(a)==len(translations)==34
p=R/'questions_en.jsonl'
with p.open('x') as f:
 for x,t in zip(a,translations):
  x['question']=t;x['translation_from']=x['id'];f.write(json.dumps(x,ensure_ascii=False)+'\n')
print('english questions',len(a),'sha256',hashlib.sha256(p.read_bytes()).hexdigest())
