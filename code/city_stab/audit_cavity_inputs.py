"""Read-only provenance and evidence audit. Never regenerates solver flags."""
from pathlib import Path
import hashlib, json, difflib, statistics, tarfile
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parents[2]/'04_Handoffs/from_22_Lab_20261015/06_Logs_luw/wallmodel'
NEW=ROOT/'isolate_stage_v2'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def analyze():
    legacy=OLD/'cont5_city_samples.json'
    new=ROOT/'iso_r2_offset_samples_a_r10.json'
    a=json.loads(legacy.read_text()); b=json.loads(new.read_text())
    assert len(a['rows'])==len(b['rows'])==80
    assert all(x['id']==y['id'] and x['after']==y['after'] for x,y in zip(a['rows'],b['rows']))
    metrics={}
    for offset in ('plus_dx','no_offset'):
        metrics[offset]={}
        for name in ('exp_ratio','sim_ratio','tke_m2s2','fluid_corners'):
            pairs=[(x['sample'][offset][name],y['sample'][offset][name]) for x,y in zip(a['rows'],b['rows'])]
            metrics[offset][name]={'mean_abs_delta':statistics.mean(abs(x-y) for x,y in pairs), 'max_abs_delta':max(abs(x-y) for x,y in pairs), 'changed':sum(x!=y for x,y in pairs)}
    src_old=OLD/'LatticeUrbanWind_repo/core/cfd_core/FluidX3D/src'
    src_new=NEW/'FluidX3D/src'
    source={}
    for name in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'):
        p=src_old/name;q=src_new/name
        source[name]={'legacy_exists':p.is_file(),'legacy_sha256':sha(p),'r2_precompile_sha256':sha(q),'same_bytes':p.read_bytes()==q.read_bytes() if p.is_file() else None}
        if p.is_file():
            hunks=[x.strip() for x in difflib.unified_diff(p.read_text().splitlines(),q.read_text().splitlines(),n=0) if x.startswith('@@')]
            source[name]['diff_hunks']=hunks
    conf_new=(NEW/'case/conf.luwpf').read_text()
    conf_old=(OLD/'LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/conf.luwpf').read_text()
    for before,after in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 500.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
        assert conf_old.count(before)==1
        conf_old=conf_old.replace(before,after)
    conf_old+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\nvk_inlet_ti = 0.1621087892\nvk_inlet_l = 100.0\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
    old_profile=OLD/'LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/wind_bc/profile.dat'
    new_profile=NEW/'case/wind_bc/profile.dat'
    old_pairs=[tuple(map(float,line.split())) for line in old_profile.read_text().splitlines()[1:]]
    new_pairs=[tuple(map(float,line.split())) for line in new_profile.read_text().splitlines()[1:]]
    new_z={round(z,6):v for z,v in new_pairs}
    profile_nodes={str(z):{'legacy':v,'r2':new_z[round(z,6)],'relative_pct':100*(new_z[round(z,6)]/v-1)} for z,v in old_pairs if round(z,6) in new_z}
    flag_candidates=[]
    for folder in (ROOT,OLD):
        for p in folder.rglob('*'):
            if p.is_file() and (p.name.startswith('flag_200') or p.name in ('flags.bin','flag.bin')):
                flag_candidates.append(str(p))
    archive={}
    for p in ROOT.glob('*.tar.gz'):
        with tarfile.open(p) as f: archive[p.name]=[m.name for m in f if m.name.endswith(('flag_200.bin','flags.bin','flag.bin'))]
    output={'native_flag_files_found':flag_candidates,'archive_flag_members':archive,
        'hash_only_flag_evidence':json.loads((ROOT/'flags_comparison.json').read_text()),
        'legacy_config_reconstruction_matches_r2':conf_old==conf_new,
        'legacy_config_reconstruction_diff':''.join(difflib.unified_diff(conf_old.splitlines(True),conf_new.splitlines(True))),
        'profile_input_rows':{'legacy':len(old_pairs),'r2':len(new_pairs)},'profile_input_node_comparison':profile_nodes,
        'inputs_sha256':{'legacy_stl':sha(OLD/'LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl'), 'r2_cropped_stl':sha(NEW/'case/proj_temp/CaseE_PF.stl'),
                         'legacy_profile':sha(OLD/'LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/wind_bc/profile.dat'),'r2_profile':sha(NEW/'case/wind_bc/profile.dat')},
        'old_vs_r2_source_partial':source,'point_metrics':metrics,'uref':{'legacy':a['uref'],'r2':b['uref']}}
    return output
if __name__=='__main__':
    out=analyze();dest=ROOT/'cavity_provenance_audit_v2.json'
    assert not dest.exists(),'refuse overwrite'
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print(dest, 'config_equal',out['legacy_config_reconstruction_matches_r2'],'flags',len(out['native_flag_files_found']))
