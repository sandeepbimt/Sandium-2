# NTP sponsored processing removal candidate

This patch is pinned by exact SHA-256 for 13 upstream core files. It removes seven complete source pairs from the shipping NTP GN source list: sponsored component downloader/installer, country campaign component map, sponsored update utility, static and dynamic takeover URL handlers, sponsored-site URL handler, and their shared source/file-loading utility.

Core service campaign parsing, registration, scheduling, updates, sponsored filesystem access, ad requests, reporting and selection bodies are removed. Legacy callback methods return empty results or do nothing for compatibility. The sponsored data implementation files are reduced to empty value/API compatibility: there is no campaign parser or wallpaper construction. The dynamic event handler keeps its Mojo receiver surface but cannot send events. The infobar decision is false with no preference mutation. Stored user data is untouched.

Ordinary background component download, data handling, wallpaper selection and custom background methods are byte-preserved by regression tests. Existing disabled-component preference keys and type names remain. This is not a claim that every string/type name disappears.

Apply after reset and the other removal transforms; its 13 core paths must be included in reset/replay. Expects exact pinned source or its own idempotent output marker; unknown source causes failure before any write. The companion Android consumer patch removes takeover bridge/UI registrations and Java classes. Neither should be presented as a verified APK until native compile, generated target/source verification, APK inspection and device tests succeed.

Validation so far: two tests cover pristine apply, exact replay, byte-preservation of ordinary/background methods, excluded sources and no-partial-write on drift; generated GN parses with actual GN. Full C++ compilation is unavailable locally. Core service no-op APIs are deliberate compatibility surfaces, not feature toggles.

ViewCounterModel sponsored counters and scheduling are also removed; ordinary random wallpaper rotation is retained.
