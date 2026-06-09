---
name: "Good first issue: Add a probe"
about: Add a new probe to Probe (e.g., value distribution, schema change).
title: "Add [PROBE_NAME] probe"
labels: ["good first issue", "enhancement", "new probe"]
---

## Add a new probe: `[PROBE_NAME]`

### What it should check

_Describe what the probe measures. Example: "Compare the value distribution (histogram) of a numeric column between old and new SQL."_

### Signature

The probe must follow the standard signature:

```python
def probe_name(adapter, old_sql, new_sql, key=None) -> ProbeResult:
```

### Checklist

- [ ] Add the probe function to `probe/probes.py`
- [ ] Register it in `ALL_PROBES` in `probe/diff.py`
- [ ] Add a severity rule in `probe/severity.py`
- [ ] Write tests in `tests/test_probes.py`
- [ ] Add a seed case in `tests/seeds/` with `setup.sql`, `old.sql`, `new.sql`, `meta.json`
- [ ] Verify `probe-bench` passes with 0 false positives
- [ ] Every finding carries a receipt (the SQL and the number)

### Resources

- See `CONTRIBUTING.md` for the development workflow
- See `CLAUDE.md` for the receipt contract and hard rules
- See existing probes in `probe/probes.py` for examples
