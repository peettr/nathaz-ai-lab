"""Correct OpenCL preprocessor nesting in fresh WALE decks."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
for base in ('E1Wv2','E1G0Wv2'):
 tag=base.replace('v2','v4');old=R/('stage_'+base);out=R/('stage_'+tag)
 assert old.exists() and not out.exists();shutil.copytree(old,out)
 p=out/'FluidX3D/src/kernel.cpp';s=p.read_text()
 k=')+"#if defined(SUBGRID) && !defined(WALE_SGS)"+R(';assert s.count(k)==1
 s=s.replace(k,')+"#ifdef SUBGRID"+R(\n)+"#ifndef WALE_SGS"+R(')
 k=')+"#ifdef WALE_SGS"+R(\n\tw=wale_omega[n];'
 assert s.count(k)==1
 s=s.replace(k,')+"#endif"+R( // !WALE_SGS Smagorinsky\n)+"#endif"+R( // SUBGRID\n)+"#ifdef WALE_SGS"+R(\n\tw=wale_omega[n];')
 k=')+"#endif"+R( // SUBGRID\n\n)+"#if defined(SRT)"';assert s.count(k)==1
 s=s.replace(k,')+"#if defined(SRT)"');p.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 (R/(tag+'_manifest.json')).write_text(json.dumps({f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
 print(tag)
