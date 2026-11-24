"""Exact vendor and host-smoke admission for the optional #1442 engine overlay."""
import json
from pathlib import Path

from restore_only_feature import POSTIMAGES, read_regular, safe, sha

ROOT = Path(__file__).resolve().parents[1]
PROOF = "raws-adblock/port1442/admission.json"
VENDOR = "brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/"
# A candidate must set this to the SHA of the independently reviewed admission.
ADMISSION_SHA256 = 'aaa02cf048e21719c5b0304dc4312d34c9a57270e03d3f53911ecaaef689fa84'

def proof():
    if ADMISSION_SHA256 is None:
        return None
    raw = read_regular(safe(ROOT, PROOF))
    if sha(raw) != ADMISSION_SHA256:
        raise ValueError("Unreviewed #1442 port admission proof")
    return json.loads(raw)

def prepare_stage(stage, feature):
    decision = proof()
    if decision is None:
        return
    if feature.identity != decision["manifest_sha256"]:
        raise ValueError("Port proof does not identify selected feature")
    receipt_path = safe(stage, "source-receipt.json")
    receipt = json.loads(read_regular(receipt_path))
    hashes = receipt["sha256"]
    writes = []
    for rel, entry in sorted(decision["staged_vendor_delta"].items()):
        if not rel.startswith(VENDOR) or rel not in hashes or rel not in feature.files:
            raise ValueError("Unreviewed #1442 vendor path")
        path = safe(stage, rel)
        data = read_regular(safe(ROOT, POSTIMAGES + "/" + entry["after"]))
        if (hashes[rel] != entry["before"] or sha(read_regular(path)) != entry["before"]
                or sha(data) != entry["after"] or feature.files[rel][1] != entry["after"]):
            raise ValueError("Unexpected #1442 vendor bytes: " + rel)
        writes.append((path, data))
        hashes[rel] = entry["after"]
    component = "components/sandium_adblock/"
    for rel in sorted(feature.generated("components/sandium_adblock")):
        if not rel.startswith(component):
            raise ValueError("Unexpected host-smoke path")
        expect = feature.files[rel][1]
        data = read_regular(safe(ROOT, POSTIMAGES + "/" + expect))
        if sha(data) != expect:
            raise ValueError("Unexpected #1442 native bytes: " + rel)
        path = safe(stage, rel)
        exists = path.exists()
        if exists != (rel in hashes) or (exists and sha(read_regular(path)) != hashes[rel]):
            raise ValueError("Unexpected old native stage file: " + rel)
        if not exists or hashes[rel] != expect:
            writes.append((path, data))
        hashes[rel] = expect
    for path, data in writes:
        # The pinned slice can lack directories for new native overlay files.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
