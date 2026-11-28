"""Analyze why CNNBranch DeepONet outperforms our Graph DeepONet."""
import json

with open(r'C:\graph-deeponet-wind\results\benchmark_gpu.json') as f:
    d = json.load(f)

cb = d['CNNBranchDeepONet']
db = d['DesignB']
da = d['DesignA']
pignn = d['PIGNN']
std = d['StandardDeepONet']
mgn = d['MeshGraphNets-64']

print("="*70)
print("ANALYSIS: Why does CNNBranch DeepONet outperform Graph DeepONet?")
print("="*70)

print("\n--- Detailed RMSE Comparison ---")
models = [('CNNBranch', cb), ('Design B', db), ('Design A', da), ('PIGNN', pignn), ('Std DeepONet', std), ('MGN-64', mgn)]
metrics = [
    ('random_overall_rmse', 'Overall'),
    ('random_near_building_rmse', 'Near-bld'),
    ('random_open_area_rmse', 'Open-area'),
    ('aligned_overall_rmse', 'Aligned'),
]

header = f"{'Model':<18}"
for _, mname in metrics:
    header += f" {mname:>10}"
header += f" {'Params':>10} {'Train':>7} {'Infer':>7}"
print(header)
print("-" * len(header))

for name, v in models:
    row = f"{name:<18}"
    for mkey, _ in metrics:
        val = v.get(mkey, float('nan'))
        row += f" {val:>10.4f}"
    row += f" {v['param_count']:>10,}"
    row += f" {v['train_time_sec']:>6.0f}s"
    row += f" {v['infer_time_ms']:>5.1f}ms"
    print(row)

# Calculate gaps
print("\n--- Gap Analysis: CNNBranch vs Design B ---")
for mkey, mname in metrics:
    cv = cb[mkey]
    bv = db[mkey]
    gap = (bv - cv) / bv * 100
    print(f"  {mname}: CNN={cv:.4f} vs B={bv:.4f} -> CNN better by {gap:.1f}%")

print("\n--- Possible Explanations ---")
print("""
1. CNN on 64x64 grid captures DENSE spatial patterns that sparse building graph misses
   - Building graph only has ~500 nodes (one per building)
   - CNN sees the full 64x64=4096 pixel spatial layout
   - Building footprint SHAPES are encoded by CNN but lost in graph nodes

2. Graph construction loses spatial information
   - Each building is collapsed to a single node with 5 features
   - Fine-grained footprint shape, orientation details are lost
   - Street widths, passages between buildings only partially captured by edge features

3. KNN interpolation in Trunk B adds noise
   - The softmax-weighted interpolation from ~5 nearest building nodes
   - May not capture the complex flow patterns between buildings
   - CNN directly operates on the full spatial field

4. BUT Graph DeepONet has advantages CNNBranch lacks:
   - Works on ANY resolution (not fixed 64x64)
   - Handles irregular, non-rectangular domains
   - Naturally generalizes across different urban layouts (graph topology)
   - These advantages don't show up in the current benchmark
   
5. PAPER STRATEGY OPTIONS:
   a) Acknowledge CNN branch is strong, position Graph DeepONet for its 
      unique capabilities (continuous query, irregular geometry, generalization)
   b) Improve graph construction (add more node features, finer granularity)
   c) Hybrid approach: CNN for spatial features + Graph for topology
""")
