from pathlib import Path
import hashlib,json,tarfile
r=Path(__file__).resolve().parent
s=r/'stage_t4/FluidX3D_on/src'
def edit(p,a,b):
 t=p.read_text();assert t.count(a)==1,(p,a,t.count(a));p.write_text(t.replace(a,b))
edit(s/'lbm.cpp','int experimental_ground_first_fluid_z = 1;','int experimental_ground_first_fluid_z = 1;\nulong experimental_ground_tau_start = 11000ul;')
edit(s/'lbm.cpp','"\\n\t#define def_ground_kappa 0.4f"','"\\n\t#define def_ground_tau_start " + to_string(experimental_ground_tau_start) + "ul"\n\t"\\n\t#define def_ground_kappa 0.4f"')
edit(s/'kernel.cpp','if(t>=11000ul) { // fixed 31000-step eqlog averaging window, actual force at every step','if(t>=def_ground_tau_start) { // configured start: smoke=0; full case=11000')
p=s/'setup.cpp';t=p.read_text();a='experimental_ground_mix_a=0.0f;';assert t.count(a)==1
t=t.replace(a,a+'\n        extern ulong experimental_ground_tau_start;\n        experimental_ground_tau_start = (ulong)std::max(0ll, (long long)run_nstep-(long long)purge_avg_steps);\n        const char* tau_start_text=std::getenv("LUW_GROUND_TAU_START");\n        if(tau_start_text) {\n            char* end=nullptr; const unsigned long long parsed=std::strtoull(tau_start_text,&end,10);\n            if(!*tau_start_text || *end || *tau_start_text==\'-\') print_error("invalid LUW_GROUND_TAU_START");\n            experimental_ground_tau_start=(ulong)parsed;\n        }\n        println("| Ground tau start | " + to_string(experimental_ground_tau_start) + " |");')
a='            std::ofstream out(parent+"/RESULTS/wall_tau_actual.csv");';assert t.count(a)==1
t=t.replace(a,'            double ground_count_total=0.0; for(size_t i=0;i<xy;i++) ground_count_total+=d->ground_tau_count.x[i];\n            println("| ground_tau_count total | " + to_string(ground_count_total, 3u) + " |");\n'+a)
a='#ifdef CITY_STABILITY_MONITOR\n            // Host flags after actual device voxelization';assert t.count(a)==1
t=t.replace(a,'''#ifdef GROUND_WALL_MODEL
            // Exact host equivalent of flat_ground_eligible using native post-BC flags.
            {
                const long long nx=Nx,ny=Ny,k=experimental_ground_first_fluid_z;
                const long long plane=nx*ny;
                ulong eligible=0ul;
                if(k>0 && k+1<Nz) for(long long y=2;y+2<ny;y++) for(long long x=2;x+2<nx;x++) {
                    const long long n=x+nx*y+plane*k, below=n-plane;
                    if((lbm.flags[n]&TYPE_BO)!=TYPE_F || (lbm.flags[below]&TYPE_BO)!=TYPE_S) continue;
                    const long long offsets[]={1,-1,nx,-nx,1+nx,-1-nx,1-nx,-1+nx};
                    bool ok=true;
                    for(const auto o:offsets) if((lbm.flags[n+o]&TYPE_BO)!=TYPE_F) {ok=false;break;}
                    if(ok) for(const auto o:offsets) { (void)o; }
                    if(ok && (lbm.flags[below+1]&TYPE_BO)==TYPE_S && (lbm.flags[below-1]&TYPE_BO)==TYPE_S &&
                       (lbm.flags[below+nx]&TYPE_BO)==TYPE_S && (lbm.flags[below-nx]&TYPE_BO)==TYPE_S) eligible++;
                }
                const ulong expected=(ulong)(Nx-4u)*(ulong)(Ny-4u);
                println("| flat_ground_eligible | measured="+to_string(eligible)+" expected_interior="+to_string(expected)+" |");
                std::filesystem::create_directories(parent+"/RESULTS");
                std::ofstream ef(parent+"/RESULTS/ground_eligibility.csv");
                ef<<"measured,expected_interior\\n"<<eligible<<","<<expected<<"\\n";
                ef.flush(); if(!ef) print_error("ground eligibility diagnostic write failed");
            }
#endif
#ifdef CITY_STABILITY_MONITOR
            // Host flags after actual device voxelization''')
t=t.replace('                    if(ok) for(const auto o:offsets) { (void)o; }\n','')
p.write_text(t)
# The full-case configs and OFF source are immutable. Only ON diagnostics changed.
m=r/'stage_t4/manifest.json';v=json.loads(m.read_text());
for name in ('kernel.cpp','setup.cpp','lbm.cpp'):v['source_sha256'][name]=hashlib.sha256((s/name).read_bytes()).hexdigest()
m.write_text(json.dumps(v,indent=2)+'\n')
b=r/'stage_t4.tar.gz';assert not b.exists()
with tarfile.open(b,'w:gz') as f:f.add(r/'stage_t4',arcname='stage_t4')
print('bundle',hashlib.sha256(b.read_bytes()).hexdigest(),'source',v['source_sha256'])
