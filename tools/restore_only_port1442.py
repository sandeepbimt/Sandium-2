"""Exact vendor and host-smoke admission for the optional #1442 engine overlay."""
import json
from pathlib import Path

from restore_only_feature import POSTIMAGES, read_regular, safe, sha

ROOT = Path(__file__).resolve().parents[1]
PROOF = "raws-adblock/port1442/admission.json"
VENDOR = "brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/"
BRIDGE = frozenset(
    "brave/components/brave_shields/core/common/adblock/rs/src/" + name
    for name in ("engine.rs", "lib.rs")
)
# A candidate must set this to the SHA of the independently reviewed admission.
ADMISSION_SHA256 = '1fcd801fb69fbe781099da9ee29cabd1f69f8599310c0482c6ddea8490fe0807'

def proof():
    if ADMISSION_SHA256 is None:
        return None
    raw = read_regular(safe(ROOT, PROOF))
    if sha(raw) != ADMISSION_SHA256:
        raise ValueError("Unreviewed #1442 port admission proof")
    return json.loads(raw)

def staged_deltas(decision):
    vendor = decision["staged_vendor_delta"]
    bridge = decision.get("staged_bridge_delta")
    if any(not rel.startswith(VENDOR) for rel in vendor):
        raise ValueError("Unreviewed #1442 vendor path")
    # The reviewed CXX interface and implementation are a single change.
    # Do not permit arbitrary additions elsewhere in the upstream bridge tree.
    if bridge is not None and set(bridge) != BRIDGE:
        raise ValueError("Unreviewed #1442 bridge path or incomplete bridge")
    return {**vendor, **(bridge or {})}


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
    for rel, entry in sorted(staged_deltas(decision).items()):
        if rel not in hashes or rel not in feature.files:
            raise ValueError("Unreviewed #1442 staged path")
        if feature.files[rel][2] != "644":
            raise ValueError("Invalid #1442 staged source mode")
        path = safe(stage, rel)
        data = read_regular(safe(ROOT, POSTIMAGES + "/" + entry["after"]))
        if (hashes[rel] != entry["before"] or sha(read_regular(path)) != entry["before"]
                or sha(data) != entry["after"] or feature.files[rel][1] != entry["after"]):
            raise ValueError("Unexpected #1442 staged bytes: " + rel)
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
