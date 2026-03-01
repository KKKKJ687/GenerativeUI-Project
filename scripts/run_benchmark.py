#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _read_metrics(item: Dict[str, Any]) -> Dict[str, Any]:
    metrics = item.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _is_success(item: Dict[str, Any]) -> bool:
    if "success" in item:
        return bool(item.get("success"))
    metrics = _read_metrics(item)
    if "success" in metrics:
        return bool(metrics.get("success"))
    return False


def _hard_violations(item: Dict[str, Any]) -> int:
    metrics = _read_metrics(item)

    if "hard_violations" in metrics:
        return max(0, _as_int(metrics.get("hard_violations"), 0))
    if "hard_violations" in item:
        return max(0, _as_int(item.get("hard_violations"), 0))

    violations = metrics.get("violations")
    if isinstance(violations, list):
        hard = 0
        for v in violations:
            if isinstance(v, dict) and str(v.get("severity", "")).upper() == "HARD":
                hard += 1
        return hard
    return 0


def _fix_rounds(item: Dict[str, Any]) -> float:
    metrics = _read_metrics(item)
    for key in ("repair_rounds", "fix_rounds", "closed_loop_rounds"):
        if key in metrics:
            return _as_float(metrics.get(key), 0.0)
    for key in ("repair_rounds", "fix_rounds", "closed_loop_rounds"):
        if key in item:
            return _as_float(item.get(key), 0.0)
    return 0.0


def _latency_ms(item: Dict[str, Any]) -> float:
    metrics = _read_metrics(item)
    if "latency" in metrics:
        return _as_float(metrics.get("latency"), 0.0)
    if "total_ms" in metrics:
        return _as_float(metrics.get("total_ms"), 0.0)
    timing = metrics.get("timing_ms")
    if isinstance(timing, dict) and "total" in timing:
        return _as_float(timing.get("total"), 0.0)

    if "latency" in item:
        return _as_float(item.get("latency"), 0.0)
    if "total_ms" in item:
        return _as_float(item.get("total_ms"), 0.0)
    return 0.0


def _has_evidence_traceability(item: Dict[str, Any]) -> bool:
    metrics = _read_metrics(item)
    if "evidence_traceable" in metrics:
        return bool(metrics.get("evidence_traceable"))
    if "evidence_traceability_rate" in metrics:
        return _as_float(metrics.get("evidence_traceability_rate"), 0.0) > 0
    if "evidence_traceable" in item:
        return bool(item.get("evidence_traceable"))
    if "evidence_traceability_rate" in item:
        return _as_float(item.get("evidence_traceability_rate"), 0.0) > 0
    return False


def aggregate_metrics(all_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for r in all_results if isinstance(r, dict)]
    total_cases = len(rows)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "success_cases": 0,
            "hard_violation_cases": 0,
            "success_rate": 0.0,
            "hard_violation_rate": 0.0,
            "violation_rate": 0.0,
            "avg_fix_rounds": 0.0,
            "avg_latency": 0.0,
            "latency": 0.0,
            "closed_loop_rounds": 0.0,
            "evidence_traceability_rate": 0.0,
        }

    success_cases = sum(1 for row in rows if _is_success(row))
    hard_violation_cases = sum(1 for row in rows if _hard_violations(row) > 0)
    evidence_cases = sum(1 for row in rows if _has_evidence_traceability(row))

    avg_fix_rounds = sum(_fix_rounds(row) for row in rows) / total_cases
    avg_latency = sum(_latency_ms(row) for row in rows) / total_cases

    success_rate = success_cases / total_cases
    hard_violation_rate = hard_violation_cases / total_cases
    evidence_traceability_rate = evidence_cases / total_cases

    return {
        "total_cases": total_cases,
        "success_cases": success_cases,
        "hard_violation_cases": hard_violation_cases,
        "success_rate": success_rate,
        "hard_violation_rate": hard_violation_rate,
        "violation_rate": hard_violation_rate,
        "avg_fix_rounds": avg_fix_rounds,
        "avg_latency": avg_latency,
        "latency": avg_latency,
        "closed_loop_rounds": avg_fix_rounds,
        "evidence_traceability_rate": evidence_traceability_rate,
    }


def aggregate_by_mode(all_results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in all_results:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("mode", "unknown"))
        groups.setdefault(mode, []).append(row)

    output: List[Dict[str, Any]] = []
    for mode, rows in sorted(groups.items(), key=lambda kv: kv[0]):
        merged = aggregate_metrics(rows)
        merged["mode"] = mode
        output.append(merged)
    return output


def build_report(all_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for r in all_results if isinstance(r, dict)]
    return {
        "summary": aggregate_metrics(rows),
        "per_mode": aggregate_by_mode(rows),
    }


def _load_results(input_path: Path) -> List[Dict[str, Any]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() == ".jsonl":
        rows: List[Dict[str, Any]] = []
        for line in input_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if isinstance(raw.get("results"), list):
            return [x for x in raw["results"] if isinstance(x, dict)]
        if isinstance(raw.get("per_case"), list):
            return [x for x in raw["per_case"] if isinstance(x, dict)]
        if isinstance(raw.get("per_mode"), list):
            return [x for x in raw["per_mode"] if isinstance(x, dict)]
        return [raw]
    raise ValueError(f"Unsupported input format: {input_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate benchmark results and generate report.json.")
    ap.add_argument("--input", required=True, help="Path to results .json or .jsonl")
    ap.add_argument("--output-dir", default="runs/latest", help="Output directory for report and optional plots/tables")
    ap.add_argument("--no-assets", action="store_true", help="Only write report.json, skip figure/table generation")
    args = ap.parse_args()

    in_path = Path(args.input).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_results(in_path)
    report = build_report(rows)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_assets:
        try:
            from make_figures import generate_figures
            from make_tables import generate_tables

            generate_figures(str(out_dir))
            generate_tables(str(out_dir))
        except Exception as e:
            print(f"WARN: report generated, but assets generation failed: {type(e).__name__}: {e}")

    print(f"OK report={out_dir / 'report.json'} total_cases={report['summary'].get('total_cases', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
