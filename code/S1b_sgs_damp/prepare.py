from pathlib import Path
import shutil,hashlib,json,tarfile,difflib
R=Path(__file__).resolve().parent
src=R.parent/'S1_sgs_damp/stage_S1'
dst=R/'stage_S1b'
assert not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=dst/'FluidX3D/src/lbm.cpp';s=p.read_text();s=s.replace('#ifdef GROUND_WALL_MODEL\nint experimental_ground_first_fluid_z = 1;', '#if defined(GROUND_WALL_MODEL) || defined(FENG_N1_GROUND_SGS_ONLY)\nint experimental_ground_first_fluid_z = 1;\n#endif\n#ifdef GROUND_WALL_MODEL\n')
# SGS-only must emit both its kernel macro and the actual index, independently of ground wall model.
s=s.replace('#ifdef FENG_N1_GROUND_SGS_ONLY\n\t"\\n\t#define FENG_N1_GROUND_SGS_ONLY"\n#endif\n#ifdef WALL_GATE0', '#ifdef WALL_GATE0')
key='\t"\\n\t#define def_ground_mix_a " + to_string(experimental_ground_mix_a,9u) + "f"\n#endif'
assert s.count(key)==1
s=s.replace(key,key+'\n#ifdef FENG_N1_GROUND_SGS_ONLY\n\t"\\n\t#define FENG_N1_GROUND_SGS_ONLY"\n\t"\\n\t#define def_ground_first_fluid_z " + to_string(experimental_ground_first_fluid_z) +\n#endif')
p.write_text(s)
p=dst/'FluidX3D/src/setup.cpp';s=p.read_text();key='        const float flat_ground_lbmu = origin_lbmu.z + units.x(z_si_offset);';assert s.count(key)==1
s=s.replace(key,key+'\n#ifdef FENG_N1_GROUND_SGS_ONLY\n        extern int experimental_ground_first_fluid_z;\n        experimental_ground_first_fluid_z=(int)std::lround(flat_ground_lbmu-origin_lbmu.z)+1;\n        println("| Feng SGS-only first fluid global z="+to_string(experimental_ground_first_fluid_z)+" |");\n#endif')
# Read back native flags (already host-side here); validate exact covered fluid and exclusion counts.
key='            initialize_profile_velocity(lbm, ground_xy, dir_x, dir_y);\n            apply_profile_boundaries(lbm, ground_xy, dir_x, dir_y, case_downstream_bc);'
assert s.count(key)==1
ins='''
#ifdef FENG_N1_GROUND_SGS_ONLY
            if(lbm.get_D()!=1u) print_error("S1b single GPU only");
            const uint feng_nx=lbm.get_Nx(),feng_ny=lbm.get_Ny(),feng_nz=lbm.get_Nz();
            std::filesystem::create_directories(parent+"/RESULTS");
            std::ofstream feng_diag(parent+"/RESULTS/feng_coverage.csv",std::ios::out|std::ios::trunc);
            feng_diag<<"global_z,fluid_covered,solid_covered,boundary_covered,outside_covered\\n";
            ulong covered=0ul,excluded_solid=0ul;
            for(uint z=0u;z<feng_nz;z++) {
                ulong fluid=0ul,solid=0ul,boundary=0ul,outside=0ul;
                for(uint y=0u;y<feng_ny;y++) for(uint x=0u;x<feng_nx;x++) {
                    const ulong n=(ulong)x+(ulong)feng_nx*((ulong)y+(ulong)feng_ny*(ulong)z);
                    const uchar type=lbm.flags[n]&0x03u;
                    const bool layer=(int)z>=experimental_ground_first_fluid_z && (int)z<experimental_ground_first_fluid_z+8;
                    if(type==TYPE_S) {if(layer) solid++;}
                    else if(type==TYPE_E) {if(layer) boundary++;}
                    else if(layer) fluid++; else outside++;
                }
                if(z<32u) feng_diag<<z<<","<<fluid<<","<<solid<<","<<boundary<<","<<outside<<"\\n";
                covered+=fluid;excluded_solid+=solid;
                if((int)z<experimental_ground_first_fluid_z || (int)z>=experimental_ground_first_fluid_z+8)
                    if(fluid!=0ul) print_error("Feng out-of-range coverage");
            }
            feng_diag.flush();
            println("| Feng SGS-only coverage | first="+to_string(experimental_ground_first_fluid_z)+
                    " fluid="+to_string(covered)+" solid excluded="+to_string(excluded_solid)+" |");
            if(covered==0ul || experimental_ground_first_fluid_z!=21) print_error("Feng coverage invalid");
#endif
'''
s=s.replace(key,key+ins);p.write_text(s)
# Existing kernel excludes TYPE_S upstream in stream_collide; explicitly exclude equilibrium flags.
manifest={str(q.relative_to(dst)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [dst/'FluidX3D/src/defines.hpp',dst/'FluidX3D/src/setup.cpp',dst/'FluidX3D/src/kernel.cpp',dst/'FluidX3D/src/lbm.cpp',dst/'case/conf.luwpf',dst/'case/wind_bc/profile.dat',dst/'case/proj_temp/CaseE_PF.stl']}
(R/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'S1b_inputs.tar.gz','w:gz') as tar:
 tar.add(dst/'FluidX3D',arcname='FluidX3D');tar.add(dst/'case',arcname='case')
for name in ('setup.cpp','lbm.cpp'):
 original=(src/'FluidX3D/src'/name).read_text().splitlines(keepends=True)
 modified=(dst/'FluidX3D/src'/name).read_text().splitlines(keepends=True)
 (R/f'{name}.diff').write_text(''.join(difflib.unified_diff(original,modified,fromfile='S1/'+name,tofile='S1b/'+name)))
print(manifest)
