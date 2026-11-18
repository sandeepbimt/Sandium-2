"""Held typed tile input hook. Not activated by native-menu/adapter.py or CI."""
from pathlib import Path
import hashlib
HERE = Path(__file__).resolve().parent
FIXTURE = HERE/'fixtures/AppMenuDragHelper.java'
# Exact Chromium 158 source fixture, not a latest-branch heuristic.
EXPECTED = 'de5acdf02cdbcc98e0446285e4745e1e06bdd980c55d7c5070a38173bf87400f'
ANCHOR = '''        for (int i = 0; i < listView.getChildCount(); ++i) {
            boolean hasImageButtons = false;'''
INSERT = '''        for (int i = 0; i < listView.getChildCount(); ++i) {
            if (listView.getChildAt(i) instanceof RawSMenuTileTargets) {
                itemViews.addAll(((RawSMenuTileTargets) listView.getChildAt(i))
                        .rawSVisibleTileTargets());
                continue;
            }
            boolean hasImageButtons = false;'''
def transform(source):
    original = FIXTURE.read_text()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED:
        raise ValueError('Unreviewed drag helper fixture')
    if original.count(ANCHOR) != 1:
        raise ValueError('Native tile input anchor changed')
    patched = original.replace(ANCHOR, INSERT, 1)
    if source not in (original, patched):
        raise ValueError('Unreviewed native drag helper')
    return patched
