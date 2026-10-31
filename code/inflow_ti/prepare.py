from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
SRC=Path('./24_Urban_Wind_LBM/06_Logs/wp1_nearwall/city_stab/stage6_noT')
for tag in 'AB':
 d=R/f'stage_{tag}'
 assert not d.exists(),d
 shutil.copytree(SRC,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 if tag=='B':
  p=d/'FluidX3D/src/setup.cpp';s=p.read_text()
  key='float sigma_lbm = 0.0f;\n    float L_lbm'
  assert s.count(key)==1
  s=s.replace(key,'float sigma_lbm = 0.0f;\n        float official_sigma_scale = 0.0f;\n        float L_lbm')
  key='const float sigma_local = cfg_.ti > 0.0f ? (cfg_.ti * u_char) : cfg_.sigma_lbm;'
  assert s.count(key)==1
  s=s.replace(key,'''// AIJ CaseE(Niigata).xls Inflow rows 2-13, ZR=250m, UR=7.8m/s.
                // p.pz is lattice z; urban flat ground is at z=20 (conf base_height).
                static constexpr float zk[] = {1.25f,2.5f,5.f,7.5f,12.5f,25.f,50.f,75.f,100.f,150.f,200.f,250.f};
                static constexpr float kr[] = {.008f,.009f,.009f,.009f,.010f,.010f,.009f,.008f,.007f,.006f,.004f,.002f};
                const float z_agl = std::max(0.0f,p.pz - 20.0f);
                float kvar = kr[0];
                if (z_agl >= zk[11]) kvar=kr[11];
                else if (z_agl > zk[0]) for (int a=0;a<11;a++) if (z_agl<=zk[a+1]) {
                    const float t=(z_agl-zk[a])/(zk[a+1]-zk[a]);
                    kvar=kr[a]+t*(kr[a+1]-kr[a]);break;
                }
                const float sigma_local = cfg_.official_sigma_scale>0.0f
                  ? cfg_.official_sigma_scale*sqrtf(2.0f*kvar/3.0f) : (cfg_.ti>0.0f ? cfg_.ti*u_char : cfg_.sigma_lbm);''')
  key='cfg.sigma_lbm = units.u(vk_inlet_settings.sigma_si);'
  assert s.count(key)==1
  s=s.replace(key,key+'\n        cfg.official_sigma_scale = units.u(7.8f); // UR, same SI->lattice mapping as baseline')
  # Source runtime config has the member too (the declaration occurs once above).
  p.write_text(s)
  # Only B changes inlet mode: code's official scale overrides TI while retaining TI and all other config.
 manifest={}
 for name in ['FluidX3D/src/defines.hpp','FluidX3D/src/setup.cpp','FluidX3D/src/kernel.cpp','case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl']:
  manifest[name]=hashlib.sha256((d/name).read_bytes()).hexdigest()
 (R/f'{tag}_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=R/f'{tag}_inputs.tar.gz'
 with tarfile.open(archive,'w:gz') as t:
  t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag,manifest,'archive',archive.stat().st_size)
