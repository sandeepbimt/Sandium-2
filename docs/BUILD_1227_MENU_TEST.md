# Build #1227: stale menu contract assertion

The actual pruning/defaults step failed before Android compilation in
`test-sandium-toolbar-refinements.py`, test
`test_grouped_menu_surfaces_preserve_body_and_actions`.

The approved four-available-row editor added `availableGrid` inside
`availableGroup` to reserve its minimum height. The older assertion still
expected `grid(availableGroup, ...)` directly. The Java implementation was
correctly updated, but this independent production-step test was missed.
Running the focused suite on the published tree reproduced the same failure.

Update that contract to require all four parts of the intended implementation:
the inner grid, four-row minimum height, editable hidden-action population, and
attachment to the original styled group. Do not change production Java, roll
back the editor, weaken grouping/color checks, or skip the test.

Add a canonical-discovery wrapper that runs the exact focused suite with a
checked exit code. Previously the aggregate runner did not discover the script;
a separately chained local command also failed to propagate its nonzero result.
The earlier focused-pass report was therefore incorrect. The wrapper makes this
suite's result mandatory in future combined test runs.

This is a deterministic test/code-contract mismatch, not a compilation failure.
Android build/runtime validation remains pending the coordinated Full run.
