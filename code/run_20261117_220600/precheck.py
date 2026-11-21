#!/usr/bin/env python3
"""Host syntax and generated OpenCL regression against frozen T5 OFF."""
import pathlib,tarfile,tempfile,subprocess,hashlib,json,os
R=pathlib.Path(__file__).resolve().parent;T5=R.parents[1]/'R21.4a_T5_caseE_WM_retry1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(R/'stage_t5.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 with tempfile.TemporaryDirectory(prefix='t11-precheck-',dir=os.environ.get('TMPDIR')) as td:
  tmp=pathlib.Path(td)
  with tarfile.open(R/'stage_t5.tar.gz') as t:t.extractall(tmp,filter='data')
  src=tmp/'stage/FluidX3D_off';setup=src/'src/setup.cpp';assert sha(setup)==json.loads((R/'setup_manifest.json').read_text())['baseline_sha256']
  setup.write_bytes((R/'setup_t11.cpp').read_bytes());assert sha(setup)==json.loads((R/'setup_manifest.json').read_text())['sha256']
  flags=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']
  subprocess.run(flags+['-fsyntax-only','src/kernel.cpp','src/setup.cpp','src/lbm.cpp'],cwd=src,check=True)
  print('SYNTAX_OK g++ -fsyntax-only kernel.cpp setup.cpp lbm.cpp',flush=True)
  (tmp/'emit.cpp').write_text('#include "kernel.cpp"\nint main(){std::cout << get_opencl_c_code();}\n')
  subprocess.run(flags+['-Isrc',str(tmp/'emit.cpp'),'-o',str(tmp/'emit')],cwd=src,check=True)
  body=subprocess.check_output([str(tmp/'emit')]);ref=(T5/'evidence/E_s101_off_actual_opencl.cl').read_bytes()
  marker=b'\n\nconst\nfloat\ndef_domain_offset_x';assert ref.count(marker)==1
  frozen=ref[:ref.index(marker)]+body
  assert frozen==ref,'generated OpenCL changed relative to T5 OFF under frozen header'
  print('OPENCL_EXACT_T5_OFF',hashlib.sha256(frozen).hexdigest(),'bytes',len(frozen),flush=True)
  print('SOURCE_DIFF_ONLY_SETUP',sha(R/'setup_t11.cpp'),flush=True)
if __name__=='__main__':main()
