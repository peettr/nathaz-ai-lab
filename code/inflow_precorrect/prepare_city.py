from pathlib import Path
p=Path(__file__).resolve().parents[1]/'city_z0/remote_city_z0.py'
s=p.read_text()
s=s.replace("R=Path('/content/luw_city_z0_r1')", "R=Path('/content/luw_city_z2c_r1')")
s=s.replace("'/content/city_z0_inputs.tar.gz'", "'/content/Gz2c_inputs.tar.gz'")
s=s.replace("print(s,flush=True)", "print(s,flush=True)")
# Previous extractor is exercised only after solver exit 0; all evidence stays in new root.
assert "luw_city_z0_r1" not in s and "city_z0_inputs.tar.gz" not in s
(Path(__file__).parent/'remote_city.py').write_text(s)
print('prepared city driver')
