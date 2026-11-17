"""Run against an existing full pinned composed source; never modify that source."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import tempfile

def load(path):
    spec = importlib.util.spec_from_file_location('composition_module', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
a = p.parse_args()
probe = load(a.repo/'experiments/navigation-diagnostics/apply-typography-policy.py')
product = load(a.repo/'.circleci/features/page-text/apply.py')
with tempfile.TemporaryDirectory() as d:
    src = Path(d)/'src'
    shutil.copytree(a.source, src)
    # Bring an older pin-compatible composition to this exact product version.
    for path, text in product.compose(src, a.repo).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    target = src/probe.PATH
    target.write_text(probe.transform(target.read_text()))
    for path, text in product.compose(src, a.repo).items():
        if path.read_text() != text:
            raise AssertionError('Probe broke product replay: '+str(path.relative_to(src)))
    assert probe.transform(target.read_text()) == target.read_text()
print('Full page-text composition unchanged with typography diagnostic present')
