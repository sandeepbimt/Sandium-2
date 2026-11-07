#!/usr/bin/env python3
"""Offline fixture tests for the pin-guarded VPN/News/Rewards policy overlay."""
from pathlib import Path
import runpy
import tempfile

module = runpy.run_path(".circleci/scripts/apply-sandium-product-suppression.py")
apply_policy_file = module["apply_policy_file"]
policies = module["POLICIES"]

with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    for relative_path, old_method, new_method, label in policies:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class Fixture {\n" + old_method + "\n}\n", encoding="utf-8")
        apply_policy_file(target, old_method, new_method, label)
        patched = target.read_text(encoding="utf-8")
        assert patched.count(new_method) == 1, label + " replacement missing"
        assert old_method not in patched, label + " upstream implementation remains"
        apply_policy_file(target, old_method, new_method, label)
        assert target.read_text(encoding="utf-8") == patched, label + " is not idempotent"

assert "return true;" in policies[0][2]
assert "return true;" in policies[1][2]
assert "return true;" in policies[2][2]
assert "sDisabledByPolicyForTesting" in policies[2][2]
print("SANDIUM_PRODUCT_SUPPRESSION_TEST=PASS; three policy gates, Rewards test override, idempotent rerun")
