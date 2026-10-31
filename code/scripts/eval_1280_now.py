#!/usr/bin/env python3
"""
Evaluate current 1280 training (best checkpoint so far) with raw-domain eval.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "references"))

from step2_raw_restore import main
import argparse

# Monkey-patch parse_args to use 1280 paths
orig_parse = main.__code__

# Just call step2_raw_restore with correct args
sys.argv = ['step2_raw_restore.py', 
            '--data-dir', 'data/full_masked_1280',
            '--results-dir', 'results/full_masked_1280/seed_1']
main()
