#!/usr/bin/env python3
"""Launch Auto V5 smoke runs from a single control JSON file.

The control file is the deterministic top-level description of a small smoke
campaign: which source configs to copy, which new run ids to create, which model
files/modules to check, and which CRC submit tier to use. By default the script
is safe and only prints the launch plan. Use --materialize to write configs and
--submit to call scripts/crc_codegen_smoke_one.sh for each run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.configs.schema import TrainConfig

BOOKKEEPING_FIELDS = {
    "run_id",
    "retry_of",
    "retry_reason",
    "retry_note",
    "retry_status",
    "retry_tier",
    "retry_cluster",
    "cluster_id",
    "idle_reason",
    "high_vram",
}

ALLOWED_TIERS = {"h100_a100_l40s_12gb", "a40_rtx6k_16gb", "a10_16gb"}


def load_control(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit("control file root must be a JSON object")
    data.setdefault("remote_root", "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3")
    data.setdefault("stage", "smoke20")
    if data["stage"] not in {"smoke20", "benchmark200"}:
        raise SystemExit(f"unknown stage: {data['stage']}")
    if "config_overrides" in data and not isinstance(data["config_overrides"], dict):
        raise SystemExit("control config_overrides must be an object")
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        raise SystemExit("control file must contain a non-empty runs list")
    seen: set[str] = set()
    for row in runs:
        if not isinstance(row, dict):
            raise SystemExit("each runs[] entry must be an object")
        for key in ("source_campaign", "source_run_id", "run_id", "model_file", "module_name", "submit_tier"):
            if not row.get(key):
                raise SystemExit(f"run entry missing required key: {key}")
        if row["run_id"] in seen:
            raise SystemExit(f"duplicate run_id: {row['run_id']}")
        seen.add(row["run_id"])
        if row["submit_tier"] not in ALLOWED_TIERS:
            raise SystemExit(f"unknown submit_tier for {row['run_id']}: {row['submit_tier']}")
        if "config_overrides" in row and not isinstance(row["config_overrides"], dict):
            raise SystemExit(f"config_overrides for {row['run_id']} must be an object")
    if not data.get("campaign"):
        raise SystemExit("control file missing campaign")
    return data


def source_config_path(local_root: Path, row: dict[str, Any]) -> Path:
    return local_root / "campaigns" / row["source_campaign"] / "runs" / row["source_run_id"] / "train_config.json"


def target_run_dir(local_root: Path, campaign: str, run_id: str) -> Path:
    return local_root / "campaigns" / campaign / "runs" / run_id


def materialize_run(local_root: Path, control: dict[str, Any], row: dict[str, Any]) -> Path:
    src = source_config_path(local_root, row)
    if not src.exists():
        raise SystemExit(f"source train_config.json not found: {src}")
    cfg = json.loads(src.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"source train_config root must be object: {src}")
    cfg = {k: v for k, v in cfg.items() if k not in BOOKKEEPING_FIELDS}
    run_id = row["run_id"]
    remote_root = str(control["remote_root"]).rstrip("/")
    campaign = control["campaign"]
    cfg["experiment_id"] = run_id
    cfg["results_dir"] = f"{remote_root}/campaigns/{campaign}/runs/{run_id}"
    cfg.update(control.get("config_overrides") or {})
    cfg.update(row.get("config_overrides") or {})
    if "batch_size" in row and row["batch_size"] is not None:
        batch_size = int(row["batch_size"])
        if batch_size < 8:
            raise SystemExit(f"batch_size below 8 is not allowed for {run_id}")
        cfg["batch_size"] = batch_size
    TrainConfig.model_validate(cfg)
    out_dir = target_run_dir(local_root, campaign, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "train_config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    note = {
        "source_campaign": row["source_campaign"],
        "source_run_id": row["source_run_id"],
        "run_id": run_id,
        "submit_tier": row["submit_tier"],
        "model_file": row["model_file"],
        "module_name": row["module_name"],
        "control_campaign": campaign,
        "metadata_rule": "bookkeeping stays outside train_config.json",
    }
    if "reason" in row:
        note["reason"] = row["reason"]
    (out_dir / "CONTROL_NOTE.txt").write_text("\n".join(f"{k}: {v}" for k, v in note.items()) + "\n")
    return out_dir


def command_env(control: dict[str, Any], row: dict[str, Any]) -> dict[str, str]:
    env = {
        "CAMPAIGN": str(control["campaign"]),
        "RUN_ID": str(row["run_id"]),
        "MODEL_FILE": str(row["model_file"]),
        "MODULE_NAME": str(row["module_name"]),
        "SUBMIT_TIER": str(row["submit_tier"]),
    }
    if control.get("remote_root"):
        env["REMOTE"] = str(control["remote_root"])
    env["STAGE"] = str(control.get("stage", "smoke20"))
    return env


def build_plan(local_root: Path, control: dict[str, Any], *, materialize: bool) -> dict[str, Any]:
    rows = []
    for row in control["runs"]:
        if materialize:
            materialize_run(local_root, control, row)
        rows.append({
            "run_id": row["run_id"],
            "source_campaign": row["source_campaign"],
            "source_run_id": row["source_run_id"],
            "model_file": row["model_file"],
            "module_name": row["module_name"],
            "submit_tier": row["submit_tier"],
            "batch_size": row.get("batch_size"),
            "command_env": command_env(control, row),
            "command": "bash scripts/crc_codegen_smoke_one.sh",
        })
    return {
        "campaign": control["campaign"],
        "remote_root": control["remote_root"],
        "stage": control.get("stage", "smoke20"),
        "summary": {"runs": len(rows)},
        "runs": rows,
    }


def submit_runs(local_root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in plan["runs"]:
        env = os.environ.copy()
        env.update(row["command_env"])
        proc = subprocess.run(
            ["bash", "scripts/crc_codegen_smoke_one.sh"],
            cwd=local_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        row_result = {
            "run_id": row["run_id"],
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
        results.append(row_result)
        if proc.returncode != 0:
            raise SystemExit(json.dumps({"failed_submit": row_result}, indent=2))
    return results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--control", type=Path, required=True)
    p.add_argument("--local-root", type=Path, default=_REPO_ROOT)
    p.add_argument("--materialize", action="store_true", help="write target train_config.json files")
    p.add_argument("--submit", action="store_true", help="submit each run through crc_codegen_smoke_one.sh")
    p.add_argument("--dry-run", action="store_true", help="print plan only; does not submit")
    p.add_argument("--plan-output", type=Path, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    control = load_control(args.control)
    plan = build_plan(args.local_root, control, materialize=args.materialize)
    if args.plan_output:
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.plan_output.write_text(json.dumps(plan, indent=2) + "\n")
    if args.submit and not args.dry_run:
        plan["submit_results"] = submit_runs(args.local_root, plan)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
