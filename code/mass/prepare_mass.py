from pathlib import Path
import shutil, tarfile, re, hashlib
R=Path(__file__).parent
source=R.parent/'bisect/stage'
for case in ('D','M1','M2'):
    dst=R/case
    if dst.exists(): raise RuntimeError('Refusing to overwrite '+str(dst))
    shutil.copytree(source,dst)
    src=dst/'FluidX3D/src'
    p=src/'kernel.cpp';s=p.read_text()
    needle='\tfor(uint k=ibb_start[n]; k<ibb_start[n+1u]; k++) {\n\t\tconst uint d=ibb_direction[k], opposite='
    assert s.count(needle)==1
    if case=='M1':
        s=s.replace(needle,'\tfloat ibb_mass_delta=0.0f;\n'+needle,1)
        anchor='\t\tfhn[opposite]=reflected;\n\t\tibb_link_force'
        assert s.count(anchor)==1
        s=s.replace(anchor,'\t\tibb_mass_delta += reflected-outgoing;\n'+anchor,1)
        anchor='\t}\n)+"#endif"+R(\n\n)+"#ifdef GROUND_WALL_MODEL"'
        assert s.count(anchor)==1
        s=s.replace(anchor,'\t}\n\t// Link-local mass compensation to the rest packet; this is experimental.\n\tfhn[0]-=ibb_mass_delta;\n)+"#endif"+R(\n\n)+"#ifdef GROUND_WALL_MODEL"',1)
    if case=='M2':
        # N=3: only corners with at least three active building links fall back to native half-way rule.
        anchor='\t\tconst float q=ibb_q[k], outgoing=ibb_previous[k];'
        assert s.count(anchor)==1
        s=s.replace(anchor,'\t\tconst bool mass_crowded=(ibb_start[n+1u]-ibb_start[n]>=3u);\n'+anchor,1)
        s=s.replace('if(t>0ul && q<0.5f) {','if(t>0ul && !mass_crowded && q<0.5f) {',1)
        s=s.replace('} else if(t>0ul && q>0.5f) {','} else if(t>0ul && !mass_crowded && q>0.5f) {',1)
    p.write_text(s)
    p=src/'setup.cpp';s=p.read_text()
    needle='            size_t bad=N; const char* component="";'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n            size_t rho_lo_cell=N,rho_hi_cell=N;',1)
    needle='                mass+=r;lo=std::min(lo,r);hi=std::max(hi,r);'
    assert s.count(needle)==1
    s=s.replace(needle,'                mass+=r;if(r<lo){lo=r;rho_lo_cell=i;}if(r>hi){hi=r;rho_hi_cell=i;}',1)
    needle='            last_step=lbm.get_t();'
    assert s.count(needle)==1
    ins='''            {
                static std::ofstream extrema(parent+"/RESULTS/mass_extrema.csv",std::ios::out|std::ios::trunc);
                static bool header=false;if(!header){extrema<<"step,kind,index,x,y,z,rho,neighbors_s,active_links,q_values,owners,previous_rho,delta_rho\\n";header=true;}
                for(int kind=0;kind<2;kind++){
                    const size_t i=kind?rho_hi_cell:rho_lo_cell;
                    if(i>=N)continue;
                    const size_t x=i%nx,y=(i/nx)%ny,z=i/(nx*ny);
                    unsigned ns=0;for(int zz=-1;zz<=1;zz++)for(int yy=-1;yy<=1;yy++)for(int xx=-1;xx<=1;xx++){
                      if(!xx&&!yy&&!zz)continue;
                      const int ax=(int)x+xx,ay=(int)y+yy,az=(int)z+zz;
                      if(ax>=0&&ay>=0&&az>=0&&ax<(int)nx&&ay<(int)ny&&az<(int)nz) ns+=((dom->flags.x[idx(ax,ay,az)]&0x03u)==TYPE_S);
                    }
                    const float previous=last_rho[i];
                    extrema<<lbm.get_t()<<','<<(kind?"max":"min")<<','<<i<<','<<x<<','<<y<<','<<z<<','<<dom->rho.x[i]<<','<<ns<<",0,none,none,"<<previous<<','<<(dom->rho.x[i]-previous)<<'\\n'<<std::flush;
                }
            }
'''
    # Link attributes joined offline from exactly same CSR, avoid GPU readback, host CSV has placeholders.
    s=s.replace(needle,ins+needle,1)
    p.write_text(s)
    p=dst/'case/conf.luwpf';s=p.read_text();assert 'run_nstep = 31000' in s
    s=s.replace('run_nstep = 31000','run_nstep = '+ ('8000' if case=='D' else '10000'))
    p.write_text(s)
    print(case,hashlib.sha256((dst/'case/wind_bc/profile.dat').read_bytes()).hexdigest())
    with tarfile.open(R/(case+'.tar.gz'),'w:gz') as t:t.add(dst,arcname='stage')
