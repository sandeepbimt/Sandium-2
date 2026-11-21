# RawS combined Sandium UI, ad-blocking and codec test

The shipping #1477 comparison base is product commit
`45dc081ae5a40bbe69b869b98b80013c5f34afec`, Chromium Android M158
`52bdd21723d5db0c9ab11716d38feac74828cf84`. On the phone, the known-good
AVC/AAC MP4 failed with MediaError 4 and the type was not advertised; the
known-good WebM produced a frame. This proves the current capability gap,
not the codecs or validity of the reported website's original media.

The combined product baseline is
`82ca4e667b0140bf080fd4d235913866685f1f4a` (tree
`ee06fb096f4635c5b571c12cc63d2c91c47ab711`). It carries the reviewed
Sandium presentation/menu and Shields controls, ad filtering,
and player popup/redirect rules. This change leaves those product sources
and all overlay bytes unchanged and adds the scoped codec profile only
when the optional private media profile is selected.

[Chromium audio/video build flags](https://www.chromium.org/audio-video/) and
[the pinned codec default](https://github.com/chromium/chromium/blob/52bdd21723d5db0c9ab11716d38feac74828cf84/build/config/features.gni)
support selecting the Chrome FFmpeg configuration without changing browser
branding. On pinned Android ARM64, the trial explicitly retains baseline
`media_use_openh264=false`, `enable_hls_demuxer=false` and
`enable_hevc_parser_and_hw_decoder=false`. The
[pinned media options](https://github.com/chromium/chromium/blob/52bdd21723d5db0c9ab11716d38feac74828cf84/media/media_options.gni)
declare these independent switches: HLS-off preserves default MPEG-2
transport-stream parsing off, and HEVC-off preserves default platform
HEVC and its optional encode/decode capabilities off. The script also
requires both resolved software H.264/H.265 WebRTC options off. These
settings do not disable Chromium's FFmpeg demuxing or Android MediaCodec
playback. If any resolved value differs or is absent, the trial stops.

Check the pinned FFmpeg Android ARM64 config headers in the prepared checkout:
MP4 demuxing must stay available, AVC/AAC decoders and parsers must switch
from off to on, and FFmpeg's HEVC decoder/parser and HLS demuxer must stay
off. The runner records config hashes and values. Full pinned checkout
and actual GN execution are still required to validate these settings.

This is not an AVC/AAC-only promise across all browser APIs:
`proprietary_codecs` is a global Chromium gate. For example, pinned
[media/gpu/BUILD.gn](https://github.com/chromium/chromium/blob/52bdd21723d5db0c9ab11716d38feac74828cf84/media/gpu/BUILD.gn)
also includes Android's NDK audio encoder under this flag, independently
of the above options. The trial does not grant distribution rights or
change any signing identity setting.

## Generate the test graph

Use exact combined baseline `82ca4e6` with the extra local codec helper
unstaged/untracked (or copy it to a clean exact baseline checkout). Supply
an independently prepared checkout carrying **the exact combined overlay** and
pinned GN/depot_tools, dependency, platform and optimization-profile inputs.
No download, production restore or APK generation is initiated by this script.

```sh
python3 tools/raws_codec_trial.py \
    --prepared-source /absolute/independent-prepared/src \
    --depot-tools /absolute/pinned/depot_tools \
    --distinct-test-identity
```

The combined CI route always uses the existing distinct test package and
signer. For a comparable local GN check, pass `--distinct-test-identity`.
The local tool composes the package argument; it does not invoke the signer.

The script refuses source/revision/recipe/args drift, reuses the existing
official-build validation, verifies resolved media and package flags, and
writes an isolated `out/RawSandiumCodecTrial/codec-trial-receipt.json` only
on successful GN verification. It does not write `out/RawSandium`,
ordinary tracked `ci/args.gn`, CI config, or any checkpoint. Existing trial
output is rejected; use a fresh independent workspace for another attempt.

## Regular RawS build

Run ordinary RawS with `run_raw_full=true` on `raw-sandium/official158`.
Set `raws_h264_aac=true` only for the private AVC/AAC media profile.
Both settings use the same checkpoint, compiler and isolated signer. Leave
all bootstrap, maintenance and final archive selectors false.
The trial verifies its sole direct parent and allows only its tool, workflow,
documentation and test files to differ from the combined baseline.

The same no-credentials compile job restores the exact immutable #1396
receipt/archive read-only and verifies the exact admitted combined browser source.
It regenerates only the worker-local graph with scoped media args. No
fallback source seed, checkpoint promotion, or continuation is possible.
The existing 30-minute compile cap remains; a timeout yields no APK.
#1477's verified compile was 1,373 seconds, so the trial has 427 seconds
of extra phase room on that run's timings. This is not a prediction:
media buildflag/FFmpeg changes and a native link can exceed that margin.

The compiler verifies the resolved trial settings and the generated
media buildflag header; the private signing handoff binds that scope and
the compiler-verified unsigned APK hash to the exact workflow, candidate commit and
unchanged combined feature manifest. It also binds the exact 14 native
smoke cases, including `incident1471-player-rules`. The existing separate
signer rechecks the binding, signs once, and verifies the same independent
package and certificate pins. Neither success nor failure writes an archive. It emits `RawSandium-Combined-Codec-Test-arm64.apk` and a receipt marked test-only and
`distribution_ready=false`; ordinary artifact names/receipts are unchanged.
The build system does not infer on-device behavior or distribution rights.

Acceptance: compare with the same offline two-format test on the same phone.
Both clips must produce a frame in the codec-enabled candidate. Verify the
menu, Shields status and user-visible popup blocking separately. Since
this APK combines codec and product changes, site behavior alone cannot
isolate the effect of a codec flag.
