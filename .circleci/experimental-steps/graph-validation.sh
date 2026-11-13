set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
OUT="$ROOT/brave-work/src/out/android_Release_arm64"
SISO_ENV="$ROOT/brave-work/src/build/config/siso/.sisoenv"
SISO_RC="$ROOT/brave-work/src/build/config/siso/.sisorc"
SISO_BACKEND="$ROOT/brave-work/src/build/config/siso/backend_config/backend.star"
test -s "$SISO_ENV" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL missing Siso .sisoenv" >&2; exit 1; }
test -s "$SISO_RC" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL missing Siso .sisorc" >&2; exit 1; }
test -s "$SISO_BACKEND" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL missing Siso backend.star" >&2; exit 1; }
grep -Fx "SISO_CREDENTIAL_HELPER=/tmp/sandium-buildbuddy-credential-helper.py" "$SISO_ENV" >/dev/null || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL Siso credential helper path mismatch" >&2; cat "$SISO_ENV" >&2; exit 1; }
SISO_ADDRESS="$(sed -n 's/^SISO_REAPI_ADDRESS=//p' "$SISO_ENV" | tail -n 1)"
SISO_INSTANCE="$(sed -n 's/^SISO_REAPI_INSTANCE=//p' "$SISO_ENV" | tail -n 1)"
test -n "$SISO_ADDRESS" && [[ "$SISO_ADDRESS" == *:443 ]] || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL invalid Siso REAPI address" >&2; cat "$SISO_ENV" >&2; exit 1; }
test "$SISO_INSTANCE" = "default" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL Siso instance differs from pinned Brave .gclient default" >&2; cat "$SISO_ENV" >&2; exit 1; }
for REQUIRED_SISO_FLAG in \
  '-reapi_keep_exec_stream' \
  '-fs_min_flush_timeout 300s' \
  '-reapi_byte_stream_read_threshold 1024' \
  '-config googlechrome,remote-link' \
  '-re_cache_enable_write=true'; do
  grep -Fq -- "$REQUIRED_SISO_FLAG" "$SISO_RC" || {
    echo "BRAVE_STAGE_CONFIG_GATE=FAIL missing Siso flag: $REQUIRED_SISO_FLAG" >&2
    cat "$SISO_RC" >&2
    exit 1
  }
done
test -x /tmp/sandium-buildbuddy-credential-helper.py || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL helper missing on this runner" >&2; exit 1; }
PYTHON_REMOTE_WRAPPER="$ROOT/brave-work/src/buildtools/reclient_cfgs/python/python_remote_wrapper"
test -x "$PYTHON_REMOTE_WRAPPER" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL Brave Python remote wrapper missing executable mode" >&2; ls -l "$PYTHON_REMOTE_WRAPPER" 2>&1 || true; exit 1; }
test "${SISO_LIMITS:-}" = "local=8,remote=80" || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL unexpected SISO_LIMITS: ${SISO_LIMITS:-unset}" >&2; exit 1; }
BRAVE_DEPOT_TOOLS="$ROOT/brave-work/src/brave/vendor/depot_tools"
test -x "$BRAVE_DEPOT_TOOLS/autoninja" || {
  echo "BRAVE_STAGE_CONFIG_GATE=FAIL Brave-managed depot_tools/autoninja missing at $BRAVE_DEPOT_TOOLS/autoninja" >&2
  ls -ld "$BRAVE_DEPOT_TOOLS" "$BRAVE_DEPOT_TOOLS/autoninja" 2>&1 || true
  exit 1
}
export PATH="$BRAVE_DEPOT_TOOLS:$PATH"
command -v autoninja >/dev/null || { echo "BRAVE_STAGE_CONFIG_GATE=FAIL autoninja missing from PATH after adding Brave depot_tools" >&2; exit 1; }
if [ "${SANDIUM_STAGE}" = "1" ]; then
  for required in build.ninja args.gn; do
    if [ ! -s "$OUT/$required" ]; then
      echo "BRAVE_BUILD_GRAPH_GATE=FAIL missing=$OUT/$required" >&2
      find "$ROOT/brave-work/src/out" -maxdepth 4 -type f \( -name build.ninja -o -name args.gn -o -name args_generated.gni \) -print 2>/dev/null | head -100 >&2 || true
      exit 1
    fi
  done
  ARGS_GENERATED="$OUT/args_generated.gni"
  test -s "$ARGS_GENERATED" || { echo "BRAVE_REMOTE_EXECUTION_CONFIG_GATE=FAIL missing $ARGS_GENERATED" >&2; exit 1; }
  grep -F 'args_generated.gni' "$OUT/args.gn" >/dev/null || { echo "BRAVE_REMOTE_EXECUTION_CONFIG_GATE=FAIL args.gn does not import args_generated.gni" >&2; cat "$OUT/args.gn" >&2; exit 1; }
  echo "=== Actual generated GN args (args_generated.gni) ==="
  grep -nE 'use_remoteexec|use_siso|use_reclient' "$ARGS_GENERATED" || true
  require_arg() {
    local name="$1" expected="$2"
    if ! grep -Eq "^[[:space:]]*${name}[[:space:]]*=[[:space:]]*${expected}[[:space:]]*$" "$ARGS_GENERATED"; then
      echo "BRAVE_REMOTE_EXECUTION_CONFIG_GATE=FAIL expected ${name}=${expected} in $ARGS_GENERATED" >&2
      echo "=== Brave .env RBE setting ===" >&2
      grep -nE '^(rbe_service|use_remoteexec)=' "$ROOT/brave-work/src/brave/.env" >&2 || true
      echo "=== generated args file ===" >&2
      grep -nE 'use_remoteexec|use_siso|use_reclient' "$ARGS_GENERATED" >&2 || true
      echo "=== args.gn imports ===" >&2
      grep -n 'args_generated.gni' "$OUT/args.gn" >&2 || true
      echo "=== end diagnostics ===" >&2
      exit 1
    fi
  }
  require_arg use_remoteexec true
  require_arg use_siso true
  require_arg use_reclient false
  echo "BRAVE_BUILD_GRAPH_GATE=PASS"
  echo "BRAVE_REMOTE_EXECUTION_CONFIG_GATE=PASS"
fi
python3 "$ROOT/.circleci/scripts/product_absence.py" --src "$ROOT/brave-work/src" --out "$OUT" --report "$ROOT/brave-apk/native-removal-report.json"
