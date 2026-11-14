# Build and packaging precheck: scope and limits

The local workspace does not contain the full Chromium source, generated Android graph, Android toolchain or compiled checkpoint. Fixture and syntax tests cannot establish Java, JNI, C++, link or APK success.

`precheck-sandium-build.py` runs only against a prepared CI source tree after the real GN generation and removal audits have succeeded. It:

1. Checks pinned Android packaging executables and actually launches `aapt version` and `apksigner version`. This is readiness, not signing/packaging validation.
2. Reads the declared upstream-reset source inputs from the removal manifest.
3. Uses the actual pinned `gn refs` graph to resolve direct non-test, non-link owners into Ninja outputs. No target names are guessed. An empty or unsafe plan fails.
4. Writes the reviewed input and target lists plus a JSON report.
5. With an explicit positive `--compile-seconds`, runs real `autoninja -strict_remote` on those outputs under a bounded deadline. It signals the process group and waits up to 30 seconds before killing on timeout. CI must leave that shutdown time and diagnostic-upload time before its hard deadline.

Default is planning only. It is safe to run in a graph diagnostic job without starting compilation. `PASS_SELECTED_TARGETS` means only those targets finished. Timeout is `INCOMPLETE_TIMEOUT` and exits 124, not green compilation. A failure records `FAILED` and logs. The script never writes an APK completion or canonical checkpoint receipt.

## Deliberate limitations

- Removed source files normally have no active owner, and the query resolves the union of remaining owners. It does **not** prove that every changed or generated file has been compiled.
- GN aggregate executable/shared-library targets and APK/AAB outputs are excluded. Source-set/static-library owner targets can still be broad and expensive; their output list must be reviewed before selecting a compile budget.
- Header/include and generated-code changes can affect other callers not in this direct-owner list. Thus this probe is an early defect detector, not replacement for the final full product build.
- The build still needs final native linking, resource merge/manifest generation, dex/R8, APK signing, ZIP/signature/package/branding and removal audits, followed by device startup/use testing. Packaging cannot be proven without an actual APK.
- Remote action-cache hits can benefit a subsequent build, but the diagnostic job does not publish compiled output to the canonical checkpoint. Do not claim its local compilation work is persisted unless an independently verified cache mechanism saves it.

## Invocation

```
python3 .circleci/scripts/precheck-sandium-build.py \
  --src "$ROOT/brave-work/src" \
  --out "$ROOT/brave-work/src/out/android_Release_arm64" \
  --manifest .circleci/features/removal-recipe.json \
  --report-dir "$ROOT/precheck-artifacts/build" \
  --job-start "$ROOT/.checkpoint-state/job-start.json"
```

Optional `--compile-seconds N` requires the same verified Siso configuration, credential helper and `BUILDBUDDY_API_KEY` as the normal build. It does not install or change these. After planning, the script validates the same-job epoch receipt and caps the requested compile time at the remaining 55-minute internal deadline minus 180 seconds for artifacts and 30 seconds for shutdown. Less than 60 seconds available yields `INCOMPLETE_NO_TIME` without compilation. This guard does not claim the whole job will finish and does not publish checkpoints.

## Verification performed

- Eight unit tests cover strict output handling, declared-source presence, timeout-not-success, selected-command exit handling and missing packaging tool rejection.
- The exact GN owner-resolution command was exercised with the official GN binary on a small real generated source-set graph.
- No full Chromium targeted compilation or actual APK validation has been performed locally.
