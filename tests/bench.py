"""Seed benchmark runner: reports catch rate and false-positive rate."""

from __future__ import annotations

import json
import os
import sys

from probe.db import DuckDBAdapter
from probe.diff import run_diff
from probe.severity import classify

SEEDS_DIR = os.path.join(os.path.dirname(__file__), "seeds")


def load_seeds() -> list[dict]:
    seeds = []
    for name in sorted(os.listdir(SEEDS_DIR)):
        seed_dir = os.path.join(SEEDS_DIR, name)
        if not os.path.isdir(seed_dir):
            continue
        meta_path = os.path.join(seed_dir, "meta.json")
        if not os.path.exists(meta_path):
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        with open(os.path.join(seed_dir, "setup.sql")) as f:
            setup_sql = f.read()
        with open(os.path.join(seed_dir, "old.sql")) as f:
            old_sql = f.read().strip()
        with open(os.path.join(seed_dir, "new.sql")) as f:
            new_sql = f.read().strip()
        meta["setup_sql"] = setup_sql
        meta["old_sql"] = old_sql
        meta["new_sql"] = new_sql
        seeds.append(meta)
    return seeds


def run_seed(seed: dict) -> dict:
    adapter = DuckDBAdapter.connect(":memory:")
    try:
        for stmt in seed["setup_sql"].split(";"):
            stmt = stmt.strip()
            if stmt:
                adapter.run(stmt)
        report = run_diff(
            adapter, seed["old_sql"], seed["new_sql"], key=seed.get("key")
        )
    finally:
        adapter.close()

    expected_sev = seed["expected_severity"]
    expected_probe = seed["expected_probe"]

    caught = False
    for r in report.results:
        if r.name == expected_probe and r.status == "changed":
            caught = True
            break

    sev_match = report.severity == expected_sev

    allowed = {expected_probe} | set(seed.get("also_fires", []))
    false_positives = []
    for r in report.results:
        actual_sev = classify(r)
        if actual_sev in ("warn", "block") and r.name not in allowed:
            false_positives.append(r.name)

    return {
        "name": seed["name"],
        "caught": caught,
        "sev_match": sev_match,
        "expected_severity": expected_sev,
        "actual_severity": report.severity,
        "expected_probe": expected_probe,
        "false_positives": false_positives,
    }


def main() -> None:
    seeds = load_seeds()
    if not seeds:
        print("No seeds found.")
        sys.exit(1)

    results = [run_seed(s) for s in seeds]
    total = len(results)
    caught = sum(1 for r in results if r["caught"])
    all_fps = []

    print(f"{'Seed':<25} {'Caught':<8} {'Sev':<12} {'FP'}")
    print("-" * 60)
    for r in results:
        sev_str = f"{r['actual_severity']}/{r['expected_severity']}"
        fp_str = ", ".join(r["false_positives"]) if r["false_positives"] else "-"
        mark = "ok" if r["caught"] else "MISS"
        print(f"{r['name']:<25} {mark:<8} {sev_str:<12} {fp_str}")
        all_fps.extend(r["false_positives"])

    print("-" * 60)
    catch_rate = f"{caught}/{total}"
    fp_count = len(all_fps)
    print(f"Catch rate:        {catch_rate}")
    print(f"False positives:   {fp_count}")

    if caught < total or fp_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
