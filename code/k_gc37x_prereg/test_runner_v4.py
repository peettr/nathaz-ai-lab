"""Runner v4 guard tests (expansion mode). Synthetic candidates N1-N4 reuse R1's real obs tables and R1 model readouts
(read-only, copied into a temp dir under new event names). Checks: prefix-of-frozen-order, batch membership, batch size,
'incomplete' lead, final/未完成 status."""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
D = Path('./16_PETW/02_Subprojects/WRF_Modeling/07_Validation/lab_K_gc37_main')
PRE = HERE.parent/'k_gc37_prereg'
class RunnerGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp()); T = json.loads((PRE/'event_times_gc37.json').read_text())['R1']
        sites = json.loads((D/'readout_R1R2_obs/inventory/sites.json').read_text())['R1']
        cls.ev = {}
        for k in ('N1', 'N2', 'N3', 'N4'):
            for suf in ('OBS_objects.csv', 'onset.csv', 'coverage.csv'):
                txt = (D/f'readout_R1R2_obs/obs/R1_{suf}').read_text().replace('\nOBS,R1,', f'\nOBS,{k},').replace('\nR1,', f'\n{k},')
                (cls.tmp/f'{k}_{suf}').write_text(txt)
            shutil.copy(D/'readout_R1R2_obs/obs/R1_frame_times.json', cls.tmp/f'{k}_frame_times.json')
            cls.ev[k] = {'event_times': T, 'station': [38.96, -95.67], 'obs_dir': str(cls.tmp), 'frame_times_dir': str(cls.tmp), 'sites_json': str(cls.tmp/'sites.json')}
        (cls.tmp/'sites.json').write_text(json.dumps({k: sites for k in cls.ev}))
        (cls.tmp/'cand.json').write_text(json.dumps({'main': [{'order': k} for k in ('N1', 'N2', 'N3', 'N4')], 'secondary': []}))
        full = {'24h': {'pairs': [[str(D/'readout_R1R2_24h'), 'R1_AI_24h_dt12', 'R1_GFS_24h_dt12', 12]]},
                '48h': {'pairs': [[str(D/'readout_R1R2_48h'), 'R1_AI_48h', 'R1_GFS_48h', 15], [str(D/'readout_R1R2_48h_dt12'), 'R1_AI_48h_dt12', 'R1_GFS_48h_dt12', 12]]},
                '72h': {'pairs': [[str(D/'readout_R1R2_72h'), 'R1_AI_72h', 'R1_GFS_72h', 12]]}}
        cls.full = full
    def run_cfg(self, events):
        c = {'mode': 'expansion', 'candidates_json': str(self.tmp/'cand.json'), 'events': events}
        p = self.tmp/'cfg.json'; p.write_text(json.dumps(c)); o = self.tmp/'out.json'
        r = subprocess.run([sys.executable, '-I', str(HERE/'run_judge_gc37_v4.py'), str(p), str(o)], capture_output=True, text=True)
        return r, (json.loads(o.read_text()) if r.returncode == 0 else None)
    def test_gap_in_order_rejected(self):
        r, _ = self.run_cfg({k: self.ev[k] for k in ('N1', 'N3')}); self.assertNotEqual(r.returncode, 0); self.assertIn('prefix', r.stderr)
    def test_cells_must_be_first_passers(self):
        e = {k: dict(self.ev[k]) for k in ('N1', 'N2', 'N3', 'N4')}; e['N2']['leads'] = self.full
        r, _ = self.run_cfg(e); self.assertNotEqual(r.returncode, 0); self.assertIn('first obs-gate passers', r.stderr)
    def test_batch_of_two_rejected_when_not_exhausted(self):
        e = {k: dict(self.ev[k]) for k in ('N1', 'N2', 'N3')}
        for k in ('N1', 'N2'): e[k]['leads'] = self.full
        r, _ = self.run_cfg(e); self.assertNotEqual(r.returncode, 0); self.assertIn('batches of 3', r.stderr)
    def test_incomplete_lead_and_unfinished_status(self):
        e = {k: dict(self.ev[k]) for k in ('N1', 'N2', 'N3', 'N4')}
        for k in ('N1', 'N2', 'N3'): e[k]['leads'] = dict(self.full)
        e['N3']['leads']['24h'] = {'incomplete': True}
        r, o = self.run_cfg(e); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(o['events']['N3']['cells']['24h']['cell'], '不判（积分不可完成）')
        self.assertEqual(o['events']['N3']['vote'], '不差于'); self.assertEqual(o['events']['N3']['pos24_64'], [None, None])
        self.assertIsNone(o['events']['N3']['gate']['exist24_64'])
        self.assertEqual(o['events']['N1']['vote'], '不差于')
        self.assertEqual(o['main']['status'], '未完成'); self.assertIsNone(o['main']['combined']); self.assertIn('N4', o['main']['next_action'])
    def test_exhausted_list_gives_final(self):
        e = {k: dict(self.ev[k]) for k in ('N1', 'N2', 'N3', 'N4')}
        for k in e: e[k]['leads'] = self.full
        r, o = self.run_cfg(e); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(o['main']['status'], 'final'); self.assertEqual(o['main']['n'], 4); self.assertEqual(o['main']['combined'], '值得继续')
if __name__ == '__main__': unittest.main()
