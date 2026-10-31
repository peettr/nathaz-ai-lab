"""Build private real-LUW Poiseuille fixture decks; no local solver."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
P=R.parent/'approach_keep'
fixture='''
#ifdef WALE_TEST_FIXTURE
void main_setup() {
 const uint nx=32u,ny=16u,nz=20u; const float nu=0.1f,F=0.00001f;
 LBM lbm(nx,ny,nz,nu,F,0.0f,0.0f);
 parallel_for(lbm.get_N(), [&](ulong n) {uint x,y,z;lbm.coordinates(n,x,y,z);if(z==0u||z==nz-1u)lbm.flags[n]=TYPE_S;});
 for(uint t=0u;t<2500u;t++) {
  lbm.run(1u);
  if(t%100u==0u||t==2499u) {
   lbm.rho.read_from_device();lbm.u.read_from_device();
   double e=0,ref=0;float rmin=1.e10f,rmax=-1.e10f,umax=0.f;
   for(uint z=1u;z<nz-1u;z++)for(uint y=0u;y<ny;y++)for(uint x=0u;x<nx;x++) {
    const ulong n=x+nx*(y+ny*z); const float r=lbm.rho[n],v=lbm.u.x[n];
    const float zz=(float)z-0.5f,H=(float)nz-2.f;
    const float ua=F*zz*(H-zz)/(2.0f*nu);
    if(!std::isfinite(r)||!std::isfinite(v)) {println("WALE_FIXTURE_NONFINITE t="+to_string(t)+" n="+to_string(n));return;}
    rmin=fmin(rmin,r);rmax=fmax(rmax,r);umax=fmax(umax,fabs(v));e+=double(v-ua)*(v-ua);ref+=double(ua)*ua;
   }
   println("WALE_FIXTURE t="+to_string(t)+" rho_min="+to_string(rmin,8u)+" rho_max="+to_string(rmax,8u)+" umax="+to_string(umax,8u)+" rel_l2="+to_string(sqrt(e/ref),8u));
  }
 }
}
#else
'''
for tag,base in [('WALE','stage_E1Wv5'),('SMAG','stage_E1G0')]:
 out=R/('stage_reg_'+tag);assert not out.exists();shutil.copytree(P/base,out,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 defs=out/'FluidX3D/src/defines.hpp';s=defs.read_text();s='#define WALE_TEST_FIXTURE\n'+s
 if tag=='SMAG':s=s.replace('#define GROUND_WALL_MODEL // experimental','//#define GROUND_WALL_MODEL // experimental')
 defs.write_text(s)
 p=out/'FluidX3D/src/setup.cpp';s=p.read_text();key='void main_setup() {';assert s.count(key)==1;s=s.replace(key,fixture+key);p.write_text(s+'\n#endif // WALE_TEST_FIXTURE\n')
 with tarfile.open(R/(tag+'_reg_inputs.tar.gz'),'w:gz') as t:t.add(out/'FluidX3D',arcname='FluidX3D')
 print(tag,hashlib.sha256(p.read_bytes()).hexdigest())
