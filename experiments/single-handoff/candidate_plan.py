"""Dormant whole-candidate plan over restored native baseline.

Replay uses the outer transaction journal; do not patch an already patched home
baseline twice. Selected by apply.proposed only when the experimental profile is explicitly enabled.
"""
from pathlib import Path
import tempfile
import importlib.util
HERE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location('sandium_candidate_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def plan(root):
    root = Path(root).resolve()
    web, home, navigation, blur, levels, prepaint = (load(name) for name in ('web', 'home', 'navigation_plan', 'native_blur', 'blur_levels', 'prepaint_background'))
    inputs = set(blur.INPUTS) | levels.INPUTS | navigation.inputs_for(root) | {web.PATH, home.TAB, home.DELEGATE, prepaint.PATH}
    with tempfile.TemporaryDirectory(prefix='sandium-candidate-plan-') as temporary:
        staged = Path(temporary)
        for relative in sorted(inputs):
            source = root / relative
            if not source.resolve().is_relative_to(root):
                raise RuntimeError('Candidate input escapes checkout: ' + relative)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text())
        result = {}
        for planner in (web.plan, home.plan, navigation.plan, blur.plan, levels.plan, prepaint.plan):
            for path, text in planner(staged).items():
                path = path.resolve()
                if not path.is_relative_to(staged):
                    raise RuntimeError('Candidate output escapes staging')
                relative = str(path.relative_to(staged))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                result[root / relative] = text
        return result
