# RawS initial EasyList asset
The existing regular RawS Full restore-only execution policy applies the exact
recipe in `../production-restore-recipe.json`. The digest-identified EasyList
bytes in `../production-postimages` are unmodified official release 202611201317.
See `../easylist-manifest.json` and `../NOTICE-EASYLIST.md`; the Chromium Android
resource also carries this notice. The original EasyList authors retain
copyright; RawS does not claim ownership of the list or the Brave crate. This
is a bounded first network-blocking build, not behavior parity with Sandium
#1442 or a commercial release.

To review the resource overlay, verify the content-addressed EasyList input,
then copy that digest-named file as easylist.txt alongside the notice and
manifest in a scratch data directory. Run resource_overlay.py with the
unmodified pinned Chromium source root and an empty scratch destination.
The APK build itself uses only approved postimages, not review input paths.
