"""Resume ZIP extraction after source-repo stat collision; never overwrite."""
import importlib.util,pathlib,zipfile,zlib,hashlib,json,traceback
spec=importlib.util.spec_from_file_location('stage','/content/stage_l264.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
p=pathlib.Path('/content/l264a100'); root=p/'AERO_ODE'
def crc(path):
 c=0
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):c=zlib.crc32(b,c)
 return c
try:
 assert p.joinpath('stage.failed').exists() and not p.joinpath('stage.done').exists()
 z=zipfile.ZipFile(stage.HTTPRange(stage.BASE+'data.zip'))
 accepted=[]
 for info in z.infolist():
  rel=pathlib.PurePosixPath(info.filename)
  if info.is_dir():continue
  if rel.is_absolute() or '..' in rel.parts:raise ValueError(rel)
  if str(rel).startswith('data/era5_test/2024/04/'):
   if rel.parts[4] not in {f'{i:02d}' for i in range(1,14)}:continue
  elif str(rel).startswith('data/hrrr_test/04/'):
   if rel.stem not in {f'{i:02d}' for i in range(1,14)}:continue
  elif str(rel).startswith('data/hrrr_stat/'):pass
  else:continue
  dest=root.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():
   size=dest.stat().st_size
   if size!=info.file_size or crc(dest)!=info.CRC:raise RuntimeError(f'EXISTING_MISMATCH {rel} size={size} expected={info.file_size}')
   print('VERIFIED_EXISTING',rel,size,flush=True)
   accepted.append((str(rel),size,'crc32:'+format(info.CRC,'08x')))
   continue
  print('EXTRACT',rel,info.file_size,flush=True)
  h=hashlib.sha256()
  with z.open(info) as src,dest.open('xb') as dst:
   for b in iter(lambda:src.read(4*1024*1024),b''):dst.write(b);h.update(b)
  accepted.append((str(rel),info.file_size,h.hexdigest()))
  (p/'stage_resume_increment.json').write_text(json.dumps(accepted,indent=2))
 assert len([r for r in accepted if r[0].startswith('data/era5_test/')])==13
 assert len([r for r in accepted if r[0].startswith('data/hrrr_test/')])>=13
 (p/'stage_resume.done').write_text(json.dumps(accepted,indent=2))
 (p/'stage.done').write_text('ok after checked collision resume\n')
except BaseException:
 (p/'stage_resume.failed').write_text(traceback.format_exc());traceback.print_exc();raise
