#!/usr/bin/env python3.10
"""Prepare a fresh diagnostic-only source tree for the frozen T9b build4 gate."""
import pathlib, shutil, hashlib, difflib, json
R=pathlib.Path(__file__).resolve().parent; B=R/'build4_20261117_1140'; A=R/'build2_stage/FluidX3D_facade_v3'; D=B/'FluidX3D_facade_v4'
assert not B.exists(); B.mkdir(); shutil.copytree(A,D)
# Expose the DDF only to the diagnostic host fixture; no change in collision semantics.
p=D/'src/lbm.hpp';s=p.read_text();anchor='\tstring device_defines() const; // returns preprocessor constants for embedding in OpenCL C code';assert s.count(anchor)==2
s=s.replace(anchor,'\tMemory<fpxx>& diagnostic_fi() { return fi; } // read-only host fixture\n'+anchor,1);p.write_text(s)
p=D/'src/setup.cpp';s=p.read_text();start=s.index('#ifdef FACADE_CUBE_GATE',s.index('void main_setup() {'));end=s.index('#ifdef WALL_GATE0',start)
fixture=r'''#ifdef FACADE_CUBE_GATE
    const uint L=24u;
    const char* shape=std::getenv("T9B_GATE_SHAPE");
    const bool channel=shape && std::string(shape)=="channel";
    const bool wall_y=std::getenv("T9B_WALL_Y")!=nullptr;
    const uint final_step=channel?1000u:300u;
    LBM gate(L,L,L,0.02f);
    for(ulong n=0;n<gate.get_N();n++) {
        uint x,y,z;gate.coordinates(n,x,y,z);
        const bool solid=channel ? (wall_y?(y==0u||y==L-1u):(x==0u||x==L-1u))
            : (x==0u||y==0u||z==0u||x==L-1u||y==L-1u||z==L-1u||
               (x>=8u&&x<16u&&y>=8u&&y<16u&&z>=8u&&z<16u));
        if(solid)gate.flags[n]=TYPE_S;
        else {gate.rho[n]=1.0f;gate.u.x[n]=wall_y?0.035f:0.0f;
              gate.u.y[n]=wall_y?0.0f:0.035f;gate.u.z[n]=channel?0.0f:0.012f;}
    }
    const std::string output=std::getenv("T9B_GATE_OUTPUT")?std::getenv("T9B_GATE_OUTPUT"):"/content/t9b_cube_trace.csv";
    std::ofstream evidence(output);if(!evidence)print_error("cannot open gate trace");
    evidence<<std::setprecision(17)
       <<"step,M_all,fluid_rho,fluid_rho_two_step,wall_link_normal_flux_abs,wall_tangential_speed_mean,wall_faces,tangent_momentum\\n";
    auto& fi=gate.lbm_domain[0]->diagnostic_fi();
    double initial_mass=0.0,previous_rho=0.0;
    for(uint step=0;step<=final_step;step++) {
        gate.run(step?1u:0u,100u);
        if(step==0u) fi.add_host_buffer();
        fi.read_from_device();gate.rho.read_from_device();gate.u.read_from_device();
        double ddf=0.0,mass=0.0,tangent=0.0,flux=0.0,px=0.0;ulong faces=0u;
        for(ulong i=0;i<fi.range();i++)ddf+=(double)fi[i];
        // Offset populations are stored relative to equilibrium weights: add N once.
        ddf+=(double)gate.get_N();
        for(uint z=0;z<L;z++)for(uint y=0;y<L;y++)for(uint x=0;x<L;x++) {
            const ulong n=gate.index(x,y,z);
            if(gate.flags[n]&TYPE_S)continue;
            const double rho=gate.rho[n];mass+=rho;
            const double ut=wall_y?gate.u.x[n]:gate.u.y[n];
            if(channel)px+=rho*ut;
            const bool xp=(gate.flags[gate.index((x+1u)%L,y,z)]&TYPE_S)!=0u;
            const bool xm=(gate.flags[gate.index((x+L-1u)%L,y,z)]&TYPE_S)!=0u;
            const bool yp=(gate.flags[gate.index(x,(y+1u)%L,z)]&TYPE_S)!=0u;
            const bool ym=(gate.flags[gate.index(x,(y+L-1u)%L,z)]&TYPE_S)!=0u;
            const bool zp=(gate.flags[gate.index(x,y,(z+1u)%L)]&TYPE_S)!=0u;
            const bool zm=(gate.flags[gate.index(x,y,(z+L-1u)%L)]&TYPE_S)!=0u;
            const uint horizontal=(uint)xp+(uint)xm+(uint)yp+(uint)ym;
            if(horizontal==1u && !zp && !zm) {
                tangent+=fabs(ut);faces++;
                // Diagnostic directed link ledger in the stored population convention.
                // Not used in the mass or momentum acceptance criteria.
                const int axis=(xp||xm)?0:1;
                const int sign=(xp||yp)?1:-1;
                const uint outward=axis==0?(sign>0?1u:2u):(sign>0?3u:4u);
                const uint inward=outward%2u?outward+1u:outward-1u;
                const ulong N=gate.get_N();
                const double out=(double)fi[(ulong)outward*N+n];
                const double in=(double)fi[(ulong)inward*N+n];
                flux+=fabs((in-out)*(double)sign);
            }
        }
        if(step==0u)initial_mass=ddf;
        evidence<<step<<','<<ddf<<','<<mass<<','<<(step?0.5*(mass+previous_rho):mass)
                <<','<<flux<<','<<(faces?tangent/faces:0.0)<<','<<faces<<','<<px<<'\\n';
        previous_rho=mass;
        if(step%20u==0u){evidence.flush();println("FACADE_GATE_STEP "+to_string(step));}
    }
    evidence.flush();return;
#endif
'''.replace('\\n\"','\n\"')
# preserve C++ escape sequence in source string literal, not actual newlines
fixture=fixture.replace('tangent_momentum\n"','tangent_momentum\\n"').replace("<<px<<'\n';","<<px<<'\\n';")
s=s[:start]+fixture+s[end:];p.write_text(s)
# Commit diagnostic-only source diff, including exactly changed files.
for name in ('src/lbm.hpp','src/setup.cpp'):
 x=(A/name).read_text().splitlines(True);y=(D/name).read_text().splitlines(True)
 (B/(name.replace('/','_')+'.diff')).write_text(''.join(difflib.unified_diff(x,y,fromfile='v3/'+name,tofile='v4/'+name)))
manifest={str(x.relative_to(D)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(D.rglob('*')) if x.is_file()}
(B/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('PREPARED',B,'FILES',len(manifest),'SETUP_SHA',manifest['src/setup.cpp'])