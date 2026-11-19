# Full Mode-U reviewed configuration boundary

Full Mode-U appends namespaced, default-off workflows to the active configuration at commit `a672821`. The compressed `full-u-parent.config.yml.gz` captures those actual ordinary jobs, workflows and parameters. Tests require each to remain structurally identical. The older original-full candidate had historical task indexes, branch names and cache expectations that no longer matched the active pipeline. It is preserved, not silently rewritten as historical evidence, in the compressed pre-full-u files below.

The current candidate and config SHA continue to describe the actual active configuration. The production hash gate remains enforced. Only historical test expectations have moved to the explicit frozen active parent; new U workflows still require independent review and service validation before activation.

Preserved uncompressed SHA256 values:

{
  "pre-full-u-candidate.yml.gz": "62e9932a9c524170d366b6949d218467768fdd7f27e9a0b4c9b34b049aa90c53",
  "pre-full-u-config.sha256.gz": "d65b90ec71477e11b9738f1c0afc9c5c5907afcc4bfb62551afeb50645f18ab8"
}
