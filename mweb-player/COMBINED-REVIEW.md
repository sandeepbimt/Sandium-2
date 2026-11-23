# RawS #1514: local ad-blocking trial

Base source tree: e602433276fbe78e975347f8ac51362a848edc71.
Pinned Chromium: 52bdd21723d5db0c9ab11716d38feac74828cf84.
The separate signed release build pin remains unchanged. Do not push this
trial or assume the signed CircleCI preset will accept it.

* **Mobile YouTube.** Reuses the narrow player metadata transform from agent
  candidate b232fa6dbde9c580ab7b78b3b98f8d11588dae4e. The final eligible
  navigation carries one browser-authored Shields boolean with the exact
  loader. The renderer commit observer requests synchronous install before
  Blink starts the response parser. Only the top-level exact HTTPS mobile
  origin is eligible. No network rule changes, broader host blocks, or
  changes to media URLs, captions, or access-error payloads. Disable stops
  future filtering for that document; reload after re-enabling. Back/Forward
  restore and execution before the real first inline script still need Android
  verification. The JS fixture tests parser, response and initial object
  assignment, not Chromium lifecycle scheduling.
* **xmaza.** One publisher-scoped mobile under-player selector, protecting
  wrappers containing media, frames, forms or dialogs. The desktop generic
  rule and popup/network rules are unchanged. Validate live slot structure,
  late insertion, Shields on/off, both player servers and play/seek.
* **Yahoo Sports.** No added rules. Existing slot matches do not attribute
  the visible creative or establish why it remained. Confirm the actual
  visible wrapper and existing styling on the same page before widening.
* **LiveMint, Al Jazeera and The Hindu.** No rule changes; logs did not show
  another actionable miss.

No raw logs, remote pushes, CI, builds, or Android/device runs.
