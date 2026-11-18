"""Dormant complete-source composition of reviewed navigation mechanisms.

Requires the normal Sandium UI/dark baseline and reviewed home lifecycle baseline.
Does not enable any profile, mutate the checkout, or claim Android verification.
"""
from pathlib import Path
import tempfile
import importlib.util
HERE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location('sandium_navigation_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def inputs_for(root):
    root = Path(root).resolve()
    bridge, dark, wallpaper, capture = (load(name) for name in ('bridge', 'dark_policy', 'wallpaper_admission', 'capture_coordinates'))
    inputs = set(bridge.INPUTS) | set(dark.patches()) | set(dark.REGISTRATION) | {wallpaper.PATH, capture.PAGE, capture.NTP, capture.CAPTURE}
    components = {dark.HELPER, 'content/browser/renderer_host/sandium_dark_policy_authority.cc'}
    for name in bridge.STAGES:
        components.update(getattr(bridge.load(name), 'COMPONENTS', {}))
    inputs.update(path for path in components if (root / path).exists())
    return inputs

def plan(root):
    root = Path(root).resolve()
    bridge, dark, wallpaper, capture = (load(name) for name in ('bridge', 'dark_policy', 'wallpaper_admission', 'capture_coordinates'))
    inputs = inputs_for(root)
    with tempfile.TemporaryDirectory(prefix='sandium-navigation-plan-') as temporary:
        staged = Path(temporary)
        for relative in sorted(inputs):
            source = root / relative
            if not source.resolve().is_relative_to(root):
                raise RuntimeError('Navigation input escapes checkout: ' + relative)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text())
        outputs = {}
        for planner in (bridge.plan, dark.plan, dark.registration_plan, wallpaper.plan, capture.plan):
            for path, text in planner(staged).items():
                path = path.resolve()
                if not path.is_relative_to(staged):
                    raise RuntimeError('Navigation output escapes staging')
                relative = str(path.relative_to(staged))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                outputs[root / relative] = text
        return outputs
