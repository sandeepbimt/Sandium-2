"""Narrow, reviewed deviation from the original bounded build command."""
def transform(cmd):
    assert 'BUILD_REASON="ACTION_FAILED_HANDOFF"' in cmd
    cmd=cmd.replace('timeout --signal=INT --kill-after=60s ', 'run_budget ')
    at='echo "BRAVE_BUILD_SLICE_BUDGET_SECONDS=$STAGE_BUILD_BUDGET_SECONDS metrics=$METRICS_FILE"'
    helper='''BUILD_BUDGET_ATTESTED=false
run_budget() {
  local duration="$1"; shift
  local marker="$STATUS_DIR/build-budget-result.json"
  rm -f "$marker"
  BUILD_BUDGET_ATTESTED=false
  local rc=0
  python3 "$ROOT/.circleci/original-full/run_budget.py" --seconds "${duration%s}" --marker "$marker" -- "$@" || rc=$?
  if [ "$rc" -eq 124 ] && python3 - "$marker" <<'PYATTEST'
import json,sys
try: d=json.load(open(sys.argv[1]))
except (OSError,ValueError): sys.exit(1)
sys.exit(0 if d == {'budget_expired': True, 'exit_code': 124} else 1)
PYATTEST
  then BUILD_BUDGET_ATTESTED=true; fi
  return "$rc"
}
'''
    cmd=cmd.replace(at,helper+at)
    cmd=cmd.replace('    BUILD_RC=124\n    echo "BRAVE_BUILD_RESUME=SKIPPED stage build budget exhausted before CAS recovery."','    echo "BRAVE_BUILD_RESUME=FAIL budget exhausted with unresolved action failure."')
    cmd=cmd.replace('      BUILD_RC=124\n      echo "BRAVE_BUILD_RESUME=SKIPPED stage build budget exhausted after CAS recovery."','      BUILD_RC=124\n      BUILD_BUDGET_ATTESTED=true\n      echo "BRAVE_BUILD_RESUME=SKIPPED stage budget exhausted after successful recovery."')
    cmd=cmd.replace('# GNU timeout returns 124 when the stage budget expires.', '# The budget supervisor attests expiry independently of child exit codes.')
    cmd=cmd.replace('elif [ "$BUILD_RC" -eq 124 ] || [ "$SECONDS" -ge "$STAGE_BUILD_DEADLINE" ]; then','elif [ "$BUILD_RC" -eq 124 ] && [ "$BUILD_BUDGET_ATTESTED" = true ]; then')
    cmd=cmd.replace('BUILD_REASON="ACTION_FAILED_HANDOFF"','BUILD_REASON="ACTION_FAILED"')
    cmd=cmd.replace('  echo "BRAVE_BUILD_COMMAND=INCOMPLETE exit=$BUILD_RC; no APK success is claimed. "\n  echo "Completed actions may be checkpointed; failed actions must remain pending for the next stage."','  echo "BRAVE_BUILD_COMMAND=FAIL exit=$BUILD_RC; stopping without archive or stage handoff."')
    cmd=cmd.replace('  echo "BUILD_HANDOFF_ALLOWED=true"','  echo "BUILD_HANDOFF_ALLOWED=$([ "$BUILD_COMMAND_SUCCEEDED" = true ] || [ "$BUILD_TIME_SLICE_EXPIRED" = true ] && echo true || echo false)"')
    cmd=cmd.replace('else\n  echo "BRAVE_BUILD_STAGE_STATUS=INCOMPLETE', 'elif [ "$BUILD_TIME_SLICE_EXPIRED" = true ]; then\n  echo "BRAVE_BUILD_STAGE_STATUS=INCOMPLETE')
    cmd += '\nif [ "$BUILD_REASON" = ACTION_FAILED ]; then exit "$BUILD_RC"; fi\n'
    # Diagnostics must never mislabel a spontaneous interrupt as timeout.
    cmd=cmd.replace('$([ "${INITIAL_BUILD_RC:-0}" -eq 124 ] && echo true || ([ "${INITIAL_BUILD_RC:-0}" -eq 130 ] && echo true || echo false))','${BUILD_BUDGET_ATTESTED:-false}')
    return cmd
