#!/usr/bin/env python3
"""Create fresh v3 diagnostic source; preserve v2 and all old results."""
import pathlib, shutil, difflib, hashlib, json
R=pathlib.Path(__file__).resolve().parent
A=R/'FluidX3D_facade_v2'; B=R/'FluidX3D_facade_v3'
assert A.is_dir() and not B.exists()
shutil.copytree(A,B)
p=B/'src/setup.cpp';s=p.read_text()
mark='void main_setup() {\n#ifdef WALL_GATE0'
assert s.count(mark)==1
cube=r'''void main_setup() {
#ifdef FACADE_CUBE_GATE
    // Closed box with internal 8^3 cube. No inlet, source or open flux.
    const uint L=24u;
    LBM gate(L,L,L,0.02f);
    for(ulong n=0;n<gate.get_N();n++) {
        uint x,y,z;gate.coordinates(n,x,y,z);
        if(x==0u||y==0u||z==0u||x+1u==L||y+1u==L||z+1u==L||
           (x>=8u&&x<16u&&y>=8u&&y<16u&&z>=8u&&z<16u)) gate.flags[n]=TYPE_S;
        else {gate.rho[n]=1.0f;gate.u.x[n]=0.035f;gate.u.y[n]=0.012f;gate.u.z[n]=0.0f;}
    }
    std::ofstream evidence("/content/facade_cube_trace.csv");
    if(!evidence) print_error("cannot open cube trace");
    evidence<<"step,total_mass,relative_drift,wall_normal_cell_flux_sum,wall_tangential_speed_mean,wall_faces\n";
    double initial_mass=0.0;
    for(uint step=0;step<=100u;step++) {
        if(step) gate.run(1u,100u); else gate.run(0u,100u);
        gate.rho.read_from_device();gate.u.read_from_device();
        double mass=0.0,normal=0.0,tangent=0.0;ulong faces=0u;
        for(uint z=1u;z+1u<L;z++)for(uint y=1u;y+1u<L;y++)for(uint x=1u;x+1u<L;x++) {
            const ulong n=gate.index(x,y,z);
            if(gate.flags[n]&TYPE_S)continue;
            mass+=(double)gate.rho[n];
            const bool xp=x+1u<L&&(gate.flags[gate.index(x+1u,y,z)]&TYPE_S);
            const bool xm=x>0u&&(gate.flags[gate.index(x-1u,y,z)]&TYPE_S);
            const bool yp=y+1u<L&&(gate.flags[gate.index(x,y+1u,z)]&TYPE_S);
            const bool ym=y>0u&&(gate.flags[gate.index(x,y-1u,z)]&TYPE_S);
            const bool zp=z+1u<L&&(gate.flags[gate.index(x,y,z+1u)]&TYPE_S);
            const bool zm=z>0u&&(gate.flags[gate.index(x,y,z-1u)]&TYPE_S);
            if((uint)xp+(uint)xm+(uint)yp+(uint)ym!=1u||zp||zm||
               x<7u||x>16u||y<7u||y>16u||z<7u||z>16u)continue;
            if(xp||xm) {normal+=(double)gate.rho[n]*gate.u.x[n]*(xp?1.0:-1.0);
                           tangent+=sqrt((double)gate.u.y[n]*gate.u.y[n]+(double)gate.u.z[n]*gate.u.z[n]);}
            else {normal+=(double)gate.rho[n]*gate.u.y[n]*(yp?1.0:-1.0);
                  tangent+=sqrt((double)gate.u.x[n]*gate.u.x[n]+(double)gate.u.z[n]*gate.u.z[n]);}
            ++faces;
        }
        if(step==0u)initial_mass=mass;
        evidence<<step<<","<<std::setprecision(17)<<mass<<","<<(mass-initial_mass)/initial_mass<<","<<normal<<","<<(faces?tangent/faces:0.0)<<","<<faces<<"\n"<<std::flush;
    }
    return;
#endif
#ifdef WALL_GATE0'''
s=s.replace(mark,cube)
mark='        const double case_preprocess_seconds = case_preprocess_clock.stop();\n        run_lbm('
assert s.count(mark)==1
export=r'''        // Diagnostic-only native full-height flag export; no geometry or physics mutation.
        if(const char* filename=std::getenv("LUW_EXPORT_FLAGS")) {
            std::ofstream f(filename,std::ios::binary);
            if(!f) print_error("cannot open flag export");
            for(ulong n=0;n<lbm.get_N();n++) {
                const uchar v=lbm.flags[n];f.write((const char*)&v,1);
            }
            f.close();if(!f) print_error("flag export write failed");
            println("FLAG_EXPORT_DONE "+std::string(filename)+" "+std::to_string(lbm.get_N()));
            if(std::getenv("LUW_FLAGS_ONLY"))return;
        }
        const double case_preprocess_seconds = case_preprocess_clock.stop();
        run_lbm('''
s=s.replace(mark,export);p.write_text(s)
# C++ main setup uses std::setprecision; setup.cpp has iomanip included via setup.hpp on this tree.
orig=(A/'src/setup.cpp').read_text().splitlines(True)
diff=''.join(difflib.unified_diff(orig,s.splitlines(True),fromfile='v2/src/setup.cpp',tofile='v3/src/setup.cpp'))
(R/'SOURCE_DIFF_v3.patch').write_text(diff)
manifest={str(x.relative_to(B)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(B.rglob('*')) if x.is_file()}
(R/'source_manifest_v3.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('v3',len(manifest),'diff lines',len(diff.splitlines()),'sha setup',manifest['src/setup.cpp'])
