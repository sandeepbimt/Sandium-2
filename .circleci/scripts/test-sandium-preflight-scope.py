#!/usr/bin/env python3
"""Protect the #842 base and ensure this branch cannot trigger CircleCI."""
import os
import subprocess

BASE=os.environ.get("SANDIUM_PREFLIGHT_BASE","c1b6a4a32caf47e1605de60e1fdffd65067ac323")
BRANCH="work/remove-chat-wallet-news-preflight"
ALLOWED={
 ".circleci/scripts/sandium-feature-dependency-preflight.py",
 ".circleci/scripts/test-sandium-feature-dependency-preflight.py",
 ".circleci/scripts/test-sandium-preflight-scope.py",
 ".github/workflows/sandium-feature-dependency-preflight.yml",
}
def git(*args):
 return subprocess.check_output(["git",*args],text=True).strip()
def main():
 if git("merge-base","HEAD",BASE)!=BASE:
  raise SystemExit("PREFLIGHT_BASE_GATE=FAIL not descended from exact #842")
 changed=set(filter(None,git("diff","--name-only",f"{BASE}...HEAD").splitlines()))
 unexpected=sorted(changed-ALLOWED)
 if unexpected: raise SystemExit("PREFLIGHT_SCOPE_GATE=FAIL "+", ".join(unexpected))
 if BRANCH in open(".circleci/config.yml",encoding="utf-8").read():
  raise SystemExit("PREFLIGHT_CIRCLECI_GATE=FAIL branch appears in CircleCI config")
 subprocess.check_call(["git","diff","--check",f"{BASE}...HEAD"])
 print(f"PREFLIGHT_BASE_GATE=PASS base={BASE}")
 print("PREFLIGHT_SCOPE_GATE=PASS only_preflight_files_changed=true")
 print("PREFLIGHT_CIRCLECI_GATE=PASS no_CircleCI_config_or_trigger_changes=true")
 print("PREFLIGHT_FEATURE_PRESERVATION_GATE=PASS existing_feature_files_untouched=true")
if __name__=="__main__":
 main()
