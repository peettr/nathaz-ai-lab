#!/usr/bin/env python3
"""Case C payload preflight. --stub launches a solver stub but creates NO result.

This is NOT the paid-run worker: production requires native voxel/mask gate,
S1 sampling, per-case field capture, CU/controller and complete ACK protocol.
"""
import argparse, csv, hashlib, json, pathlib, subprocess, sys, tarfile

CASES = ('0D', '1D', '2D')

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', type=pathlib.Path, required=True)
    ap.add_argument('--work', type=pathlib.Path, required=True)
    ap.add_argument('--solver', type=pathlib.Path, required=True)
    ap.add_argument('--stub', action='store_true')
    args = ap.parse_args()
    assert args.stub, 'production not implemented: refuse scientific solve'
    manifest = json.loads((args.payload/'STAGING.json').read_text())
    for case in CASES:
        label = 'caseC_' + case
        dest = args.work/label
        dest.mkdir(parents=True, exist_ok=False)
        archive = args.payload/(label + '.tar.gz')
        assert sha(archive) == manifest['cases'][case]['tar_sha256']
        with tarfile.open(archive) as t:
            names = [x.name for x in t.getmembers()]
            assert all(x.startswith(label + '/') and '..' not in pathlib.PurePosixPath(x).parts for x in names)
            t.extractall(args.work, filter='data')
        deck = dest/'conf.luwpf'
        profile = dest/'wind_bc/profile.dat'
        stl = dest/'proj_temp'/(label+'_PF.stl')
        assert sha(deck) == manifest['cases'][case]['deck_sha256']
        assert sha(profile) == manifest['cases'][case]['profile_sha256']
        assert sha(stl) == manifest['cases'][case]['stl_sha256']
        assert args.solver.is_file()
        log = dest/'stub_solver.log'
        with log.open('w') as out:
            result = subprocess.run([str(args.solver), str(deck)], cwd=dest, stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        assert result.returncode == 0, (case, result.returncode)
        record = {'case':case, 'deck':str(deck), 'profile':str(profile), 'stl':str(stl),
                  'solver_log':str(log), 'stub_only':True, 'solver_exit':result.returncode,
                  'scientific_result':False}
        (dest/'stub_ack.json').write_text(json.dumps(record, indent=2))
        print('STUB_ACK',json.dumps(record),flush=True)
    print('STUB_WORKER_COMPLETE_NO_SCIENTIFIC_OUTPUT',flush=True)

if __name__ == '__main__': main()
