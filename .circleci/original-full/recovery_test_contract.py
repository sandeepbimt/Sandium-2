"""Assert the exceptional branch affects only seed entry and APK-complete exit."""
from copy import deepcopy

RECOVERY = 'fix/1416-apk-recovery'
BUILD = 'brave-android-staged-build'
KEY = ('sandium-official-handoff-v1-work/1402-approved-ui-'
       '6a283962-1ca0-413a-999a-cd56a7c3f3cd-stage-1')


def normalize_normal_branch(mixed, frozen):
    """Assert permitted additions, then compare all unrelated YAML verbatim."""
    result = deepcopy(mixed)
    original = frozen['jobs'][BUILD]['steps']
    steps = result['jobs'][BUILD]['steps']
    seed = next(i for i, step in enumerate(steps)
                if 'Restore exact #1416 Stage 1 checkpoint' in str(step))
    block = steps.pop(seed)['when']
    expected_guard = {'equal': [RECOVERY, '<< pipeline.git.branch >>']}
    assert block['condition'] == {
        'and': [{'equal': [1, '<< parameters.stage_index >>']}, expected_guard]
    }
    assert block['steps'][0]['restore_cache']['keys'] == [KEY]
    assert 'resume-official-1416.py preverify' in block['steps'][1]['run']['command']
    assert steps[seed-1]['when']['condition']['and'].pop() == {'not': expected_guard}
    for index, step in enumerate(steps):
        if 'resume-official-1416.py' in str(step):
            assert 'resume-official-1394.py' in str(step)
            assert RECOVERY in str(step)
            steps[index] = deepcopy(original[index])
        elif 'halt-after-recovery-apk.sh' in str(step):
            assert RECOVERY in step['run']['command']
            steps[index]['run']['command'] = original[index]['run']['command']
    for entry in result['workflows']['sandium-full-mode']['jobs']:
        filters = entry[BUILD]['filters']['branches']['only']
        assert filters.count(RECOVERY) == 1
        filters.remove(RECOVERY)
    return result
