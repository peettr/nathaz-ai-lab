#!/usr/bin/env python3
"""Single-cycle D-X2 recovery; import the frozen v2 scientific runner unchanged."""
import argparse
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/infer_b1_blackwell_8_v2/infer_b1_blackwell_8_v2.py')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True, choices=('N1', 'N3', 'N4'))
    parser.add_argument('--lead', required=True, choices=('24h', '48h', '72h'))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('frozen_science', SOURCE)
    science = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(science)
    science.ROOT = ROOT
    assert science.sha(science.PARAM) == science.EXPECTED
    assert any(d.platform == 'gpu' for d in science.jax.devices())
    config = json.loads((ROOT/'event_times_bbox_gc37x.json').read_text())['events']
    lead = config[args.event]['leads'][args.lead]
    cycle = lead['t0'].replace('-', '').replace(':', '').replace('T', '')[:10]
    science.run_one(args.event, args.lead, cycle, int(lead['length_h']//6), config[args.event]['domain'])


if __name__ == '__main__':
    main()
