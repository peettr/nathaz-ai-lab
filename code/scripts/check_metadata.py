"""Check metadata for wind direction info."""
import json

with open(r'C:\graph-deeponet-wind\data\urbantales\raw\metadata_ideal.json', encoding='utf-8-sig') as f:
    data = json.load(f)

print("Keys in first case:")
for k, v in data[0].items():
    if isinstance(v, list):
        print(f"  {k}: [list of {len(v)} items]")
    else:
        print(f"  {k}: {v}")

print("\nWind directions in first 10 cases:")
for d in data[:10]:
    name = d.get("Folder Name", "?")
    wd = d.get("Wind Direction", "MISSING")
    config = d.get("Config", "?")
    print(f"  {name}: wind_dir={wd} config={config}")

# Count unique wind directions
wds = set()
for d in data:
    wds.add(str(d.get("Wind Direction", "")))
print(f"\nUnique wind directions: {sorted(wds)}")
