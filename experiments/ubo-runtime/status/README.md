# Visible engine state inside Shields

Read-only diagnostic row directly below the existing Shields status, preserving
all controls and blocked-resource counts. No extra screen or user action.

Native JNI reads the actual profile owner, generation ACK, runtime availability
and fallback flags. It never selects an engine or changes a preference. UI labels:

- Engine: Brave native (including OTR or runtime-disabled profiles)
- Engine: uBlock Origin (selected owner and current native eligibility)
- uBlock Origin: updating rules
- Engine: Brave fallback
- Engine: starting (up to12seconds)
- Engine unavailable: restart Sandium

This is runtime state, not certification that a particular page's ads were blocked.
The popup refreshes every500ms only while open, updates text only on changes and
uses a small existing-header row. There is no permanent background polling.
English diagnostic strings are intentional for this experimental candidate;
shipping localization remains future work.

Apply LAST after phone popup/layout transforms and runtime layers:

```
python3 experiments/ubo-runtime/status/apply.py --core "$SRC/brave"
```

Reset FIRST before reversing runtime/product source transforms:

```
python3 experiments/ubo-runtime/status/apply.py --core "$SRC/brave" --reset
```

An owned before/after receipt protects the4modified Java/JNI/layout files and
rejects unknown edits. Tests use actual pinned sources, repeat/reset and grouped
phone-popup composition. Native/Java compile and actual visual/device QA remain
required; these source tests do not constitute a successful APK result.
