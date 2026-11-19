# #1402 notification reset ownership provenance

This migration binds the existing #1394 and #1401 resource inventories to recipe
8f207c76cf57d3217ea6dab193eb1dc503dedf86. Only two Java reset owners and the
coordinator's exact Brave patch mapping were added. All removal groups, sixteen
steps, GN and resource declarations are unchanged. The old recipe is preserved
as a SHA-verified compressed fixture; proof.json preserves original inventory
provenance and file hashes. The regression reconstructs both old inventory files
byte-for-byte and checks every non-provenance field, including all resource
classifications, evidence, and pinned source definitions.

There remain 328 original rows (320 exact exceptions, eight removed owned
resources) and 644 supplemental exact exceptions. Rendered lint XML is identical.
This is not new lint execution or an Android compilation claim. No exception,
resource classification, upstream pin or suppression policy is changed.
