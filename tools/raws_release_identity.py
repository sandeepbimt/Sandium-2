"""Identity checks for an independently signed RawS Android test package.

No private key, password, or signing configuration is part of this module.
The certificate pin must come from the project's independently provisioned key,
not from the APK being checked.
"""

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

APPLICATION_ID = "io.github.sandeepbimt.raws"
DISPLAY_LABEL = "Sandium"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SIGNING_DIGEST_LINE = re.compile(
    r"^Signer #\d+ certificate SHA-256 digest: ([0-9A-Fa-f]{64})$",
    re.MULTILINE,
)
_PACKAGE_LINE = re.compile(r"^package: name='([^']+)'", re.MULTILINE)
_LABEL_LINE = re.compile(r"^application-label:'([^']*)'$", re.MULTILINE)


def compose_gn_args(baseline):
    """Use Chromium's pinned public-manifest GN arg without changing baseline."""
    if re.search(r"^\s*chrome_public_manifest_package\s*=", baseline, re.MULTILINE):
        raise ValueError("RawS manifest package already assigned")
    return baseline.rstrip("\n") + (
        f'\nchrome_public_manifest_package = "{APPLICATION_ID}"\n'
    )


def expected_fingerprint(value):
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("An independent lowercase RawS SHA-256 certificate pin is required")
    return value


def verify_package_metadata(badging):
    if re.search(r"^application-debuggable\b", badging, re.MULTILINE):
        raise ValueError("RawS release package is debuggable")
    if _PACKAGE_LINE.findall(badging) != [APPLICATION_ID]:
        raise ValueError("Unexpected RawS Android application ID")
    if _LABEL_LINE.findall(badging) != [DISPLAY_LABEL]:
        raise ValueError("Unexpected default RawS application label")


def verify_identity_reports(badging, certificates, expected_sha256):
    expected = expected_fingerprint(expected_sha256)
    verify_package_metadata(badging)
    if [m.lower() for m in _SIGNING_DIGEST_LINE.findall(certificates)] != [expected]:
        raise ValueError("RawS app must have exactly one matching project signing certificate")
    return {
        "apk_application_id": APPLICATION_ID,
        "apk_application_label": DISPLAY_LABEL,
        "apk_signer_cert_sha256": expected,
        "apk_project_identity_verified": True,
    }


def verify_release_identity(apk, aapt2, apksigner, expected_sha256, *, env=None):
    """Check actual artifact metadata and signature, never an unsigned input."""
    expected_fingerprint(expected_sha256)
    badging = subprocess.check_output(
        [str(aapt2), "dump", "badging", str(apk)],
        env=env, text=True, timeout=120,
    )
    certificates = subprocess.check_output(
        [str(apksigner), "verify", "--print-certs", str(apk)],
        env=env, text=True, timeout=120,
    )
    return verify_identity_reports(badging, certificates, expected_sha256)


def sign_release_locally(apk, output, sdk, keystore, alias, expected_sha256, *,
                         expected_input_sha256, env=None):
    """Use only on a trusted signer host, never as a remote build action.

    The caller must provision the project keystore and both passwords through
    its protected secret storage. The input APK is not sent to any service.
    Publish nothing until this function returns a verified receipt.
    """
    expected_fingerprint(expected_sha256)
    runtime = os.environ if env is None else env
    secrets = ("RAWS_KEYSTORE_PASSWORD", "RAWS_KEY_PASSWORD")
    if not all(runtime.get(k) for k in secrets):
        raise ValueError("The project signing passwords are not provisioned")
    apk, output, sdk, keystore = map(Path, (apk, output, sdk, keystore))
    if not apk.is_file() or not keystore.is_file() or not alias:
        raise ValueError("The candidate APK, project keystore and signing alias are required")
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing to overwrite an existing signed APK")
    if (not isinstance(expected_input_sha256, str)
            or _SHA256.fullmatch(expected_input_sha256) is None):
        raise ValueError("An exact candidate APK digest is required")
    with apk.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected_input_sha256:
            raise ValueError("Candidate APK does not match its verified build receipt")
    public_env = {key: runtime[key] for key in ("PATH", "JAVA_HOME", "LANG", "LC_ALL")
                  if key in runtime}
    signer_env = {**public_env, **{key: runtime[key] for key in secrets}}
    aapt2, apksigner, zipalign = (sdk / name for name in ("aapt2", "apksigner", "zipalign"))

    def run(*command, signing=False):
        # Do not print SDK diagnostic output or propagate signing secrets.
        return subprocess.check_output([str(x) for x in command], text=True,
                                       stderr=subprocess.STDOUT, timeout=180,
                                       env=signer_env if signing else public_env)

    verify_package_metadata(run(aapt2, "dump", "badging", apk))
    try:
        run(zipalign, "-c", "-P", "16", "4", apk)
        with tempfile.TemporaryDirectory(prefix=".raws-signed-", dir=output.parent) as folder:
            candidate = Path(folder) / "release.apk"
            run(apksigner, "sign", "--ks", keystore, "--ks-key-alias", alias,
                "--ks-pass", "env:RAWS_KEYSTORE_PASSWORD", "--key-pass",
                "env:RAWS_KEY_PASSWORD", "--v4-signing-enabled", "false",
                "--out", candidate, apk, signing=True)
            run(zipalign, "-c", "-P", "16", "4", candidate)
            receipt = verify_release_identity(candidate, aapt2, apksigner, expected_sha256,
                                               env=public_env)
            with candidate.open("rb") as stream:
                receipt["apk_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
            receipt["apk_input_sha256"] = expected_input_sha256
            # Atomic, exclusive promotion; unlike replace(), never overwrites.
            os.link(candidate, output)
            return receipt
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError("RawS local signing or validation failed; no APK published") from None
