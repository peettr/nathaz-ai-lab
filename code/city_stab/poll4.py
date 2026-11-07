from pathlib import Path
R=Path("/content/luw_stage6_noT_r2_1016")
for p in sorted(R.rglob("*")):
    if p.is_file() and ("RESULTS" in str(p) or p.suffix in (".json",".exit",".log") or "extract" in p.name):
        s=p.stat().st_size
        if s<200_000_000: print(s, p.relative_to(R))