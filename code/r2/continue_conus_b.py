"""Use the frozen V1 batch engine with only model/cohort/output substitutions for CONUS."""
from pathlib import Path
s=Path('/content/continue_v1_a.py').read_text()
replacements={
 "from earth2studio.models.px import StormCast":"from earth2studio.models.px import StormCastCONUS",
 "OUT=R/'r2_v1_main.jsonl'; LOG=R/'r2_segment_a_groups.jsonl'; DONE=R/'r2_segment_a.done'":"OUT=R/'r2_conus_main.jsonl'; LOG=R/'r2_segment_b_groups.jsonl'; DONE=R/'r2_segment_b.done'",
 "R/'segment_a_manifest.csv'":"R/'segment_b_manifest.csv'",
 "assert len(rows)==30 and sum(x['group']=='v1' for x in rows)==20 and sum(x['group']=='control' for x in rows)==10":"assert len(rows)==18 and sum(x['group']=='conus' for x in rows)==12 and sum(x['group']=='control' for x in rows)==6",
 "StormCast.load_model(StormCast.load_default_package()":"StormCastCONUS.load_model(StormCastCONUS.load_default_package()",
 "'v1'":"'conus'",
 "r2a_{eid}_L{lead}_s{seed}.zarr":"r2b_{eid}_L{lead}_s{seed}.zarr",
 "segment='A'":"segment='B'",
 "SEGMENT_A_DONE":"SEGMENT_B_DONE",
}
for before,after in replacements.items():
 assert before in s,(before,'missing engine token')
 s=s.replace(before,after)
assert "r2_v1_main.jsonl" not in s and "r2a_{eid}" not in s
exec(compile(s,'/content/continue_conus_b_generated.py','exec'),{'__name__':'__main__'})
