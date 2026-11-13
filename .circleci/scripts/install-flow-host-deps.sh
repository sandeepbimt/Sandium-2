#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?}"
SRC_DIR="$ROOT/brave-work/src"
APT_CACHE_DIR="$ROOT/.apt-cache"
  # Host packages are installed only after source sync/configuration succeeds.
  # Keep both apt indexes and downloaded .deb archives in the CircleCI cache.
  cd "$ROOT/brave-work"
  APT_DEB_COUNT_BEFORE="$(find "$APT_CACHE_DIR/archives" -maxdepth 1 -type f -name '*.deb' | wc -l | tr -d ' ')"
  APT_CACHE_SIZE_BEFORE="$(du -sh "$APT_CACHE_DIR/archives" 2>/dev/null | awk '{print $1}')"
  echo "PPBAS_APT_CACHE_BEFORE deb_count=$APT_DEB_COUNT_BEFORE archive_size=${APT_CACHE_SIZE_BEFORE:-0}"
  # Instrument Chromium's locale-generation boundary. The previous CircleCI
  # logs terminate immediately after "Generation complete" with exit 1, but
  # upstream emits no explicit marker proving whether locale-gen returned 0.
  INSTALL_DEPS_PY="$SRC_DIR/build/install-build-deps.py"
  test -s "$INSTALL_DEPS_PY" || {
    echo "PPBAS_LOCALE_DIAGNOSTICS=FAIL missing $INSTALL_DEPS_PY" >&2
    exit 1
  }
  python3 - "$INSTALL_DEPS_PY" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
marker = "PPBAS_LOCALE_DIAGNOSTICS=INSTALLED"
if marker in source:
    print(marker)
else:
    helper_anchor = "def install_locales():\n"
    helper = (
        "def _sandium_locale_gen(command):\n"
        "    logger.info(\"PPBAS_LOCALE_GEN_START command=%r\", command)\n"
        "    try:\n"
        "        subprocess.check_call(command)\n"
        "    except subprocess.CalledProcessError as exc:\n"
        "        logger.error(\"PPBAS_LOCALE_GEN_FAIL returncode=%s command=%r\", exc.returncode, command)\n"
        "        raise\n"
        "    logger.info(\"PPBAS_LOCALE_GEN_PASS command=%r\", command)\n"
        "\n"
    )
    if source.count(helper_anchor) != 1:
        raise SystemExit("PPBAS_LOCALE_DIAGNOSTICS=FAIL unexpected install_locales() definition")
    if source.count('subprocess.check_call(["sudo", "locale-gen"])') != 1:
        raise SystemExit("PPBAS_LOCALE_DIAGNOSTICS=FAIL unexpected locale-gen invocation count")
    if source.count('subprocess.check_call(["sudo", "locale-gen", locale])') != 1:
        raise SystemExit("PPBAS_LOCALE_DIAGNOSTICS=FAIL unexpected per-locale invocation count")
    if source.count("    install_locales()\n    return 0") != 1:
        raise SystemExit("PPBAS_LOCALE_DIAGNOSTICS=FAIL unexpected main() completion block")
    source = source.replace(helper_anchor, helper + helper_anchor, 1)
    source = source.replace(
        'subprocess.check_call(["sudo", "locale-gen"])',
        '_sandium_locale_gen(["sudo", "locale-gen"])', 1
    )
    source = source.replace(
        'subprocess.check_call(["sudo", "locale-gen", locale])',
        '_sandium_locale_gen(["sudo", "locale-gen", locale])', 1
    )
    source = source.replace(
        "    install_locales()\n    return 0",
        "    install_locales()\n    logger.info(\"PPBAS_INSTALL_BUILD_DEPS_MAIN_COMPLETE\")\n    return 0", 1
    )
    source += "\n# " + marker + "\n"
    path.write_text(source, encoding="utf-8")
    print(marker)
PY

  # Instrument the exact Python entry point as well as main(). The prior
  # log proved main() completed, but did not prove what sys.exit(main()) received.
  python3 - "$INSTALL_DEPS_PY" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
marker = "PPBAS_ENTRYPOINT_DIAGNOSTICS=INSTALLED"
anchor = 'if __name__ == "__main__":\n    sys.exit(main())'
replacement = '''if __name__ == "__main__":
    logger.info("PPBAS_ENTRYPOINT_BEGIN")
    try:
        _sandium_main_result = main()
        logger.info(
            "PPBAS_MAIN_RETURN value=%r type=%s",
            _sandium_main_result,
            type(_sandium_main_result).__name__,
        )
    except BaseException as exc:
        logger.exception(
            "PPBAS_MAIN_EXCEPTION type=%s value=%r",
            type(exc).__name__,
            exc,
        )
        raise
    logger.info("PPBAS_SYS_EXIT_REQUEST code=%r", _sandium_main_result)
    try:
        sys.exit(_sandium_main_result)
    except SystemExit as exc:
        logger.info("PPBAS_SYSTEM_EXIT code=%r", exc.code)
        raise
'''
if marker not in source:
    if source.count(anchor) != 1:
        raise SystemExit(
            "PPBAS_ENTRYPOINT_DIAGNOSTICS=FAIL expected exactly one sys.exit(main()) entry point"
        )
    source = source.replace(anchor, replacement.rstrip(), 1)
    source += "\n# " + marker + "\n"
    path.write_text(source, encoding="utf-8")
    print(marker)
else:
    required = [
        "PPBAS_ENTRYPOINT_BEGIN",
        "PPBAS_MAIN_RETURN",
        "PPBAS_SYS_EXIT_REQUEST",
        "PPBAS_SYSTEM_EXIT",
    ]
    missing = [item for item in required if item not in source]
    if missing:
        raise SystemExit(
            "PPBAS_ENTRYPOINT_DIAGNOSTICS=FAIL marker exists but instrumentation is incomplete: "
            + ",".join(missing)
        )
    print(marker + " already present")
PY

  APT_LOG="$ROOT/ppbas-install-build-deps.log"
  APT_START_TS="$(date +%s)"
  set +e
  ./src/build/install-build-deps.sh --android 2>&1 | tee "$APT_LOG"
  APT_PIPE_STATUS=( "${PIPESTATUS[@]}" )
  set -e
  APT_END_TS="$(date +%s)"
  APT_EXIT_CODE="${APT_PIPE_STATUS[0]:-125}"
  TEE_EXIT_CODE="${APT_PIPE_STATUS[1]:-125}"
  echo "PPBAS_INSTALLER_RETURNED python_exit=$APT_EXIT_CODE tee_exit=$TEE_EXIT_CODE elapsed_seconds=$((APT_END_TS - APT_START_TS))"
  if [ "$APT_EXIT_CODE" -ne 0 ] || [ "$TEE_EXIT_CODE" -ne 0 ]; then
    APT_FAILURE_CODE="$APT_EXIT_CODE"
    [ "$APT_FAILURE_CODE" -ne 0 ] || APT_FAILURE_CODE="$TEE_EXIT_CODE"
    echo "PPBAS_APT_INSTALL=FAIL python_exit=$APT_EXIT_CODE tee_exit=$TEE_EXIT_CODE elapsed_seconds=$((APT_END_TS - APT_START_TS))" >&2
    echo "PPBAS_DPKG_AUDIT_BEGIN" >&2
    sudo dpkg --audit 2>&1 || true
    echo "PPBAS_DPKG_AUDIT_END" >&2
    echo "PPBAS_APT_CHECK_BEGIN" >&2
    sudo apt-get check 2>&1 || true
    echo "PPBAS_APT_CHECK_END" >&2
    echo "PPBAS_APT_LOG_TAIL_BEGIN" >&2
    tail -n 120 "$APT_LOG" >&2 || true
    echo "PPBAS_APT_LOG_TAIL_END" >&2
    exit "$APT_FAILURE_CODE"
  fi
  rm -f "$APT_LOG"
  # Measure the APT archive cache without find|wc|tr or du|awk pipelines.
  # Under set -euo pipefail, a non-zero find/du status can abort PPBAS after
  # the dependency installer has succeeded, hiding the real post-install cause.
  if ! APT_CACHE_METRICS="$(python3 - "$APT_CACHE_DIR/archives" <<'PY'
import os
import sys

directory = sys.argv[1]
try:
    count = 0
    total_bytes = 0
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name.endswith(".deb") and entry.is_file(follow_symlinks=False):
                count += 1
                total_bytes += entry.stat(follow_symlinks=False).st_size
except OSError as exc:
    print(
        "PPBAS_APT_CACHE_METRICS=FAIL path=%s error=%s"
        % (directory, exc),
        file=sys.stderr,
    )
    raise SystemExit(1)

print("%d %d" % (count, total_bytes))
PY
  )"; then
    echo "PPBAS_APT_CACHE_METRICS=FAIL; archive cache measurement failed after installer success." >&2
    exit 1
  fi
  read -r APT_DEB_COUNT_AFTER APT_CACHE_BYTES_AFTER <<< "$APT_CACHE_METRICS"
  APT_CACHE_SIZE_AFTER="$(python3 - "$APT_CACHE_BYTES_AFTER" <<'PY'
import sys
print("%.1fMiB" % (int(sys.argv[1]) / (1024 * 1024)))
PY
  )"
  echo "PPBAS_APT_CACHE_METRICS=PASS deb_count_before=$APT_DEB_COUNT_BEFORE deb_count_after=$APT_DEB_COUNT_AFTER archive_size_after=$APT_CACHE_SIZE_AFTER"
  echo "PPBAS_APT_INSTALL=PASS elapsed_seconds=$((APT_END_TS - APT_START_TS))"


echo "FLOW_HOST_DEPS=PASS stage=${BRAVE_STAGE_INDEX:?}"
