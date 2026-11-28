import os, pathlib, shutil, sys, subprocess
arm,*files=sys.argv[1:]
root=pathlib.Path('/groups/kareem/[用户]/L26_21_DAFOAM_20261117_cube_adj')
out=root/'logs'
for filename in files:
 src=pathlib.Path(filename)
 if not src.is_file(): continue
 n=src.stat().st_size+4096
 def used(paths):
  return sum(int(row.split()[0]) for row in subprocess.check_output(['du','-sB1','--',*map(str,paths)],text=True).splitlines())
 if used([out])+n>int((root/'logs/return_cap_bytes').read_text()):
  print(f'SKIP_RETURN {arm} {src.name} bytes={n}', flush=True)
  if src.suffix in ('.json','.jsonl') or src.name=='fvSchemes': raise SystemExit(86)
  continue
 dst=out/(arm+'_'+src.name); tmp=dst.with_suffix(dst.suffix+'.part')
 with src.open('rb') as inp,tmp.open('wb') as f:
  shutil.copyfileobj(inp,f);f.flush();os.fsync(f.fileno())
 tmp.replace(dst)
 print(f'RETURN {dst.name} bytes={dst.stat().st_size}',flush=True)
