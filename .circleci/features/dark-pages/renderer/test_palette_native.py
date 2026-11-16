"""Native engine routing regression: no custom color flattening remains."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_route',here/'apply.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'src';shutil.copytree(here/'fixtures',root);m.apply(root)
 for suffix in ('graphics_context.cc','graphics_context.h'):
  rel='third_party/blink/renderer/platform/graphics/'+suffix
  assert (root/rel).read_bytes()==(here/'fixtures'/rel).read_bytes(), suffix
 paint=(root/'third_party/blink/renderer/core/paint/paint_auto_dark_mode.h').read_text()
 assert 'style.ForceDark() || style.SandiumPaletteEnabled()' in paint
 assert 'sandium_palette' not in paint
 view=(root/'third_party/blink/renderer/core/paint/view_painter.cc').read_text()
 assert 'auto_dark_mode.enabled = true' in view
 assert 'sandium_palette' not in view
 assert 'SandiumPaletteColor' not in ''.join(p.read_text() for p in root.rglob('*.cc'))
print('Native GraphicsContext byte-identical to pinned source; custom flattening absent.')
