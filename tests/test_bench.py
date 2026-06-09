"""Test that the seed benchmark passes: 5/5 catch rate, 0 false positives."""

from tests.bench import load_seeds, run_seed


def test_all_seeds_load():
    seeds = load_seeds()
    assert len(seeds) == 5


def test_catch_rate_is_perfect():
    seeds = load_seeds()
    results = [run_seed(s) for s in seeds]
    missed = [r["name"] for r in results if not r["caught"]]
    assert missed == [], f"Missed seeds: {missed}"


def test_zero_false_positives():
    seeds = load_seeds()
    results = [run_seed(s) for s in seeds]
    fps = {r["name"]: r["false_positives"] for r in results if r["false_positives"]}
    assert fps == {}, f"False positives: {fps}"


def test_severity_matches():
    seeds = load_seeds()
    results = [run_seed(s) for s in seeds]
    mismatches = [
        f"{r['name']}: got {r['actual_severity']}, expected {r['expected_severity']}"
        for r in results if not r["sev_match"]
    ]
    assert mismatches == [], f"Severity mismatches: {mismatches}"


def test_each_seed_individually():
    """Run each seed and assert it catches the expected probe."""
    seeds = load_seeds()
    for seed in seeds:
        result = run_seed(seed)
        assert result["caught"], (
            f"{result['name']}: expected {result['expected_probe']} "
            f"to fire but it didn't"
        )
        assert result["sev_match"], (
            f"{result['name']}: expected {result['expected_severity']} "
            f"but got {result['actual_severity']}"
        )
        assert not result["false_positives"], (
            f"{result['name']}: false positives: {result['false_positives']}"
        )
