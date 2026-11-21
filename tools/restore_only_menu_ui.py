"""Exact Android path inventory for the reviewed Sandium menu presenter.

This file grants no path-prefix admission. The recipe validates every admitted
byte and the Android graph checks these same files on their actual GN actions.
"""
MENU_INTERNAL = 'chrome/browser/ui/android/appmenu/internal'
MENU_JAVA_DIR = MENU_INTERNAL + '/java/src/org/chromium/chrome/browser/ui/appmenu/'
MENU_RESOURCE_DIR = MENU_INTERNAL + '/java/res/'
MENU_PARITY_TRACKED = frozenset((MENU_JAVA_DIR + 'AppMenu.java',))
MENU_PARITY_JAVA = frozenset(MENU_JAVA_DIR + name for name in (
    'SandiumPagedMenu.java', 'SandiumMenuState.java',
    'RawSParityMenuCatalog.java', 'RawSParityMenuPreferences.java',
))
MENU_PARITY_RESOURCES = frozenset(MENU_RESOURCE_DIR + name for name in (
    'values/sandium_menu_colors.xml',
    'values-night/sandium_menu_colors.xml',
    'values/sandium_menu_strings.xml',
    'drawable/raws_sandium_menu_add_home.xml',
    'drawable/raws_sandium_menu_bookmark.xml',
    'drawable/raws_sandium_menu_bookmark_added.xml',
    'drawable/raws_sandium_menu_bookmarks.xml',
    'drawable/raws_sandium_menu_desktop.xml',
    'drawable/raws_sandium_menu_downloads.xml',
    'drawable/raws_sandium_menu_exit.xml',
    'drawable/raws_sandium_menu_find.xml',
    'drawable/raws_sandium_menu_group.xml',
    'drawable/raws_sandium_menu_history.xml',
    'drawable/raws_sandium_menu_home.xml',
    'drawable/raws_sandium_menu_install.xml',
    'drawable/raws_sandium_menu_new_tab.xml',
    'drawable/raws_sandium_menu_private_tab.xml',
    'drawable/raws_sandium_menu_reader.xml',
    'drawable/raws_sandium_menu_recent.xml',
    'drawable/raws_sandium_menu_reload.xml',
    'drawable/raws_sandium_menu_save.xml',
    'drawable/raws_sandium_menu_settings.xml',
    'drawable/raws_sandium_menu_share.xml',
    'drawable/raws_sandium_menu_shred.xml',
    'drawable/raws_sandium_menu_site.xml',
    'drawable/raws_sandium_menu_translate.xml',
))
