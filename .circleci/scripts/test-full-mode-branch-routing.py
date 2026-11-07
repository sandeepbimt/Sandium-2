#!/usr/bin/env python3
"""Guard CircleCI routing so the product-suppression branch always uses Full Mode."""
from pathlib import Path

config = Path(".circleci/config.yml").read_text(encoding="utf-8")
old_branch = "feature/sandium-origin-feature-suppression-full"
new_branch = "feature/sandium-remove-rewards-news-vpn"
assert config.count(new_branch) >= 10, "new branch routing entries are incomplete"

full = config.split("  sandium-full-mode:", 1)[1].split("  sandium-fast-mode:", 1)[0]
assert new_branch in full, "branch is missing from Full Mode workflow"
assert full.count("- " + new_branch) == 5, "branch must be present in all five Full Mode stage filters"

fast = config.split("  sandium-fast-mode:", 1)[1]
fast_when = fast.split("    jobs:", 1)[0]
assert new_branch in fast_when and old_branch in fast_when, "Fast Mode exclusion must cover both forced-Full branches"
fast_filters = fast.split("    jobs:", 1)[1]
assert "- " + new_branch not in fast_filters, "branch must not be admitted by Fast Mode stage filters"

assert config.count('|| [ "${CIRCLE_BRANCH:-}" = "' + new_branch + '" ]; then') == 3, (
    "all three shell-level mode gates must force this branch to Full Mode"
)
prepare = Path(".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
for flag in ("enable_brave_rewards:false", "enable_brave_news:false",
             "enable_brave_vpn_v1:false", "enable_brave_vpn_v2:false"):
    assert flag in prepare, "missing GN disable flag: " + flag
print("SANDIUM_FULL_MODE_BRANCH_ROUTING_TEST=PASS; five stages, no Fast Mode route, three shell gates")
