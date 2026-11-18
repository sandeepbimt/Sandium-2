"""Dormant staged bridge planner. Reads real source; never writes to the checkout.

Call only after the separately reviewed home baseline has been planned/applied.
This is source integration, not profile activation or an Android build.
"""
import importlib.util
from pathlib import Path
import tempfile
HERE = Path(__file__).resolve().parent
STAGES = ('holder', 'holder_safety', 'holder_retention', 'eligibility',
          'java_adapter', 'native_adapter', 'ui_gate',
          'content_registration', 'java_registration')
INPUTS = ('chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java', 'chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java', 'chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java', 'chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/Layout.java', 'chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/StaticLayout.java', 'chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java', 'chrome/android/java/src/org/chromium/chrome/browser/tab/TabImpl.java', 'chrome/android/java/src/org/chromium/chrome/browser/ui/RootUiCoordinator.java', 'chrome/browser/android/compositor/compositor_view.cc', 'chrome/browser/android/compositor/compositor_view.h', 'chrome/browser/tab/BUILD.gn', 'chrome/browser/tab/java/src/org/chromium/chrome/browser/tab/TabObserver.java', 'content/browser/BUILD.gn', 'content/public/browser/BUILD.gn')

def load(name):
    spec = importlib.util.spec_from_file_location('handoff_bridge_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def plan(root):
    root = Path(root).resolve()
    home = load('home')
    if home.TAB_HELPER not in (root / home.TAB).read_text():
        raise RuntimeError('Apply reviewed home baseline before the native bridge')
    modules = [load(name) for name in STAGES]
    inputs = set(INPUTS)
    # Preserve existing component files so registration can reject conflicting content.
    for module in modules:
        for name in getattr(module, 'COMPONENTS', {}):
            if (root / name).exists():
                inputs.add(name)
    with tempfile.TemporaryDirectory(prefix='sandium-bridge-plan-') as temporary:
        staged = Path(temporary)
        for relative in sorted(inputs):
            source = root / relative
            if not source.resolve().is_relative_to(root):
                raise RuntimeError('Bridge input escapes checkout: ' + relative)
            text = source.read_text()  # missing real input fails; no fixture substitution
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        outputs = {}
        for module in modules:
            for target, text in module.plan(staged).items():
                target = target.resolve()
                if not target.is_relative_to(staged):
                    raise RuntimeError('Bridge module output escapes staging')
                relative = str(target.relative_to(staged))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
                outputs[root / relative] = text
        return outputs
