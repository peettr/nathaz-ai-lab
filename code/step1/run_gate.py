# L26.12 第 1 步闸门：Pangu-Weather 24h ONNX 能否在中间层截成两段，且串联与整网输出逐点一致（相对差 <1e-4）
# 在 Colab VM 上跑；结果写 /content/out/gate.json，进度写 /content/inc.jsonl，结束写 /content/run.done
import json, os, sys, time, subprocess, hashlib, traceback
T0 = time.time()
OUT = "/content/out"; os.makedirs(OUT, exist_ok=True)
INC = "/content/inc.jsonl"
def log(**k):
    k["t"] = round(time.time() - T0, 1)
    print(json.dumps(k, ensure_ascii=False), flush=True)
    with open(INC, "a") as f: f.write(json.dumps(k, ensure_ascii=False) + "\n")
res = {"step": "L26.12 step1 gate", "criterion": "max|A∘B - full| / max|full| < 1e-4 per output"}
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "onnx", "onnxruntime-gpu", "xarray", "zarr<3", "gcsfs"], check=True)
    import numpy as np, onnx, onnxruntime as ort, xarray as xr
    from onnx import helper
    log(stage="pip_done", ort=ort.__version__, providers=ort.get_available_providers())
    W = "/content/pangu_weather_24.onnx"
    URL = "https://sites.ecmwf.int/repository/ai-models/test-data/pangu-weather/pangu_weather_24.onnx"
    if not os.path.exists(W):
        subprocess.run(["wget", "-q", "-O", W, URL], check=True)
    h = hashlib.sha256(open(W, "rb").read()).hexdigest()
    res["weights"] = {"url": URL, "bytes": os.path.getsize(W), "sha256": h}
    log(stage="weights", **res["weights"])

    # ---- ERA5 输入（WeatherBench2 公开 zarr，与原文同源）
    ds = xr.open_zarr("gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr",
                      storage_options={"token": "anon"}, chunks=None)
    t0 = np.datetime64("2019-09-01T12:00")   # Dorian 成熟期（原文图 2 所用个例附近）
    levs = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]
    def grab(t):
        s = ds.sel(time=t)
        up = np.stack([s[v].sel(level=levs).values for v in
                       ["geopotential", "specific_humidity", "temperature", "u_component_of_wind", "v_component_of_wind"]]).astype(np.float32)
        sf = np.stack([s[v].values for v in
                       ["mean_sea_level_pressure", "10m_u_component_of_wind", "10m_v_component_of_wind", "2m_temperature"]]).astype(np.float32)
        lat = s["latitude"].values
        if lat[0] < lat[-1]:      # Pangu 要求 90→-90
            up = up[..., ::-1, :]; sf = sf[..., ::-1, :]
        lon = s["longitude"].values
        assert abs(lon[0]) < 1e-6 and up.shape[-2:] == (721, 1440), (lon[0], up.shape)
        # WB2 的 level 维是 (var, level, lat, lon)；sel 后 level 顺序按 levs
        return np.ascontiguousarray(up), np.ascontiguousarray(sf)
    up, sf = grab(t0)
    up24, sf24 = grab(t0 + np.timedelta64(24, "h"))
    log(stage="era5", up=list(up.shape), sf=list(sf.shape), msl_min=float(sf[0].min()))

    # ---- 整网推理
    so = ort.SessionOptions(); so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    prov = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    m = onnx.load(W)
    in_names = [i.name for i in m.graph.input]; out_names = [o.name for o in m.graph.output]
    feeds = {in_names[0]: up, in_names[1]: sf}
    sess = ort.InferenceSession(W, so, providers=prov)
    full = sess.run(None, feeds)
    del sess
    res["io"] = {"inputs": in_names, "outputs": out_names}
    # 合理性：24h 预报与 ERA5 t+24 的 MSL、Z500 RMSE
    rm = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))
    res["sanity"] = {"msl_rmse_Pa": rm(full[1][0], sf24[0]), "z500_rmse_m2s2": rm(full[0][0, 5], up24[0, 5]),
                     "persist_msl_rmse_Pa": rm(sf[0], sf24[0]), "persist_z500_rmse_m2s2": rm(up[0, 5], up24[0, 5])}
    log(stage="full_run", **res["sanity"])

    # ---- 在拓扑中点附近选切点：找主干张量（被后续节点消费），切点 = 节点序号 k
    nodes = list(m.graph.node); N = len(nodes)
    init = {i.name for i in m.graph.initializer}
    producer = {}
    for i, n in enumerate(nodes):
        for o in n.output: producer[o] = i
    def boundary(k):
        # 第 k 个节点之前产出、在 >=k 的节点里被消费的张量（含原始输入）
        need = set()
        for n in nodes[k:]:
            for x in n.input:
                if not x or x in init: continue
                p = producer.get(x, -1)
                if p < k: need.add(x)
        for o in out_names:
            if producer.get(o, -1) < k: need.add(o)
        return sorted(need)
    cands = []
    for k in range(int(N * 0.35), int(N * 0.65)):
        b = boundary(k)
        if all(x not in in_names for x in b):
            cands.append((len(b), abs(k - N // 2), k, b))
    cands.sort()
    res["n_nodes"] = N
    res["cut_candidates_top5"] = [(c[2], c[0]) for c in cands[:5]]
    if not cands:
        raise RuntimeError("中点附近找不到不依赖原始输入的切点")
    _, _, K, B = cands[0]
    log(stage="cut", k=K, boundary=B, op_before=nodes[K - 1].op_type, op_after=nodes[K].op_type)

    # ---- 段 A：输入 → 边界张量（作为输出跑出来）
    import copy
    mA = copy.deepcopy(m)
    del mA.graph.output[:]
    mA.graph.output.extend([helper.make_tensor_value_info(x, onnx.TensorProto.FLOAT, None) for x in B])
    sA = ort.InferenceSession(mA.SerializeToString(), so, providers=prov)
    mid = sA.run(B, feeds); del sA, mA
    res["boundary_shapes"] = {x: list(v.shape) for x, v in zip(B, mid)}
    log(stage="segA", shapes=res["boundary_shapes"])

    # ---- 段 B：边界张量 → 原输出（只保留 >=K 的节点及其所需权重）
    # 常量节点的输出不作为 B 的输入，而把产生它们的 Constant 节点复制进 B
    constB = [x for x in B if nodes[producer[x]].op_type == "Constant"]
    keep = [i for i, x in enumerate(B) if x not in constB]
    B = [B[i] for i in keep]; mid = [mid[i] for i in keep]
    nodesB = [nodes[producer[x]] for x in constB] + nodes[K:]
    res["boundary_used"] = {x: [list(v.shape), str(v.dtype)] for x, v in zip(B, mid)}
    gB = helper.make_graph(nodesB, "pangu_B",
                           [helper.make_tensor_value_info(x, helper.np_dtype_to_tensor_dtype(v.dtype), list(v.shape)) for x, v in zip(B, mid)],
                           list(m.graph.output),
                           [i for i in m.graph.initializer if any(i.name in n.input for n in nodesB)])
    mB = helper.make_model(gB, opset_imports=m.opset_import); mB.ir_version = m.ir_version
    sB = ort.InferenceSession(mB.SerializeToString(), so, providers=prov)
    outB = sB.run(None, dict(zip(B, mid)))
    rel = [float(np.max(np.abs(a - b)) / np.max(np.abs(b))) for a, b in zip(outB, full)]
    res["rel_maxdiff"] = dict(zip(out_names, rel))
    # 附加：主干张量加小扰动是否只造成有限、小幅改变（干预可行性的粗检，不进判据）
    main = max(range(len(B)), key=lambda i: mid[i].size)
    pert = [x.copy() for x in mid]; pert[main] = pert[main] * 1.01
    outP = sB.run(None, dict(zip(B, pert)))
    res["perturb_1pct_main"] = {"tensor": B[main], "finite": bool(all(np.isfinite(o).all() for o in outP)),
                                "msl_maxabs_change_Pa": float(np.max(np.abs(outP[1] - outB[1])))}
    res["pass"] = bool(all(r < 1e-4 for r in rel))
    log(stage="segB", rel=res["rel_maxdiff"], passed=res["pass"], perturb=res["perturb_1pct_main"])
except Exception as e:
    res["error"] = repr(e); res["trace"] = traceback.format_exc(); res["pass"] = False
    log(stage="error", error=repr(e))
res["wall_s"] = round(time.time() - T0, 1)
json.dump(res, open(f"{OUT}/gate.json", "w"), ensure_ascii=False, indent=1, default=str)
open("/content/run.done", "w").write("done\n")
