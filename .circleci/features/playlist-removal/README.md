# Android Playlist compile-out

Pinned Brave 44a84b1. Apply feature-local transformations after existing Sandium UI overlays; set enable_playlist=false and enable_playlist_webui=false. Reset manifest paths before replay of earlier overlays on a restored checkpoint. Playlist Java/JNI, AAR dependencies, activities/services, preferences/menu entry and toolbar observer/media detection are removed from compilation. Ordinary media remains unchanged; upstream checkout and legal notices remain.

Test: `python test.py --source /path/to/pinned/brave-core` exercises git-object fixtures, idempotence, exclusions and atomic rejection of unknown edits. This is not Android compilation or device validation. Integrated overlays and GN graph must be validated before publishing; sources can retain harmless feature keys/shared strings without compiling service implementations.
