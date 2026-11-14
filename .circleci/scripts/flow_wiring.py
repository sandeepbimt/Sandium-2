"""Validate active Full-only pipeline's generated YAML subset and actual overlay shell commands.

This intentionally accepts only direct run-command wrappers used by Full, not a
partial general YAML interpreter. Unknown/conditional wiring fails closed. No
PyYAML dependency is introduced into build-stage Python.
"""
from pathlib import Path
import re
import shlex

ORDER = [f'product-overlay-{i}-0.sh' for i in range(24,30)] + ['graph-validation.sh','remote-smoke.sh','full-bounded-build.sh']
REQUIRED = {
 'product-overlay-24-0.sh': ['apply-sandium-branding.sh'],
 'product-overlay-25-0.sh': ['apply-sandium-adblock-engine-race.py','apply-sandium-filter-subscriptions.py','apply-sandium-filter-bootstrap.py'],
 'product-overlay-26-0.sh': ['apply-sandium-page-transition-full.py'],
 'product-overlay-27-0.sh': ['apply-sandium-homepage-adblock-warmup.py','apply-sandium-download-concurrency.py','apply-sandium-welcome-setup.py','test-sandium-homepage-adblock-warmup.py','test-sandium-download-concurrency.py','test-sandium-welcome-setup.py','test-sandium-page-transition-full.py','verify-sandium-vanilla-brave.py'],
 'product-overlay-28-0.sh': ['apply-sandium-shields-two-state.py','apply-sandium-adblock-engine-race.py','test-sandium-shields-two-state.py','test-sandium-adblock-engine-race.py','test-sandium-filter-subscriptions.py','test-sandium-filter-bootstrap.py','apply-sandium-adblock-resources.py','test-sandium-adblock-resources.py'],
 'product-overlay-29-0.sh': ['apply-sandium-ui-prune.py','test-sandium-ui-prune.py','apply-sandium-visible-branding.py','test-sandium-visible-branding.py','apply-sandium-native-theme.py','test-sandium-native-theme.py','apply-sandium-scroll-status-bar.py','test_status_underlap_patch.py','apply-sandium-shields-popup.py','test-sandium-shields-popup.py'],
}


def shell_invocations(path):
    text=path.read_text();result=[];heredoc=None
    if not re.search(r'^set -euo pipefail$',text,re.M):raise ValueError(f'{path.name}: fail-fast shell required')
    for line in text.splitlines():
        if heredoc:
            if line.strip()==heredoc:heredoc=None
            continue
        line=line.strip()
        if not line or line.startswith('#'):continue
        if re.match(r'(if|elif|else|fi|case|esac|for|while|until|function)\b',line):
            raise ValueError(f'{path.name}: conditional overlay execution is unsupported')
        match=re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?",line)
        if match:heredoc=match.group(1)
        tokens=shlex.split(line,comments=True)
        if line=='set -euo pipefail':continue
        if len(tokens)==1 and re.match(r'^(ROOT|SRC|CORE)=',tokens[0]):
            if '$(' in line or '`' in line:raise ValueError('Command substitution in wrapper assignment unsupported')
            continue
        if not tokens or tokens[0] not in ('python3','bash'):
            raise ValueError(f'{path.name}: unsupported shell command in overlay wrapper')
        if len(tokens)>1 and tokens[0] in ('python3','bash') and tokens[1].startswith(('.circleci/scripts/','$ROOT/.circleci/scripts/','${ROOT}/.circleci/scripts/','.circleci/tests/')):
            if any(t in (';','&&','||','|','&') for t in tokens):raise ValueError('Compound/optional overlay invocation unsupported')
            result.append((Path(tokens[1]).name,tokens[2:]))
    if heredoc:raise ValueError('Unclosed shell heredoc')
    return result


def verify_full_wiring(repo):
    repo=Path(repo);text=(repo/'.circleci/config.yml').read_text()
    section=re.search(r'^jobs:\s*\n(.*?)(?=^[A-Za-z][A-Za-z0-9_-]*:|\Z)',text,re.M|re.S)
    if not section:raise ValueError('Missing jobs section')
    if 'product-overlay-30-0.sh' in text:raise ValueError('Removal overlay is forbidden for UI-only product')
    chunks=re.split(r'^  ([A-Za-z0-9_-]+):\s*\n',section.group(1),flags=re.M)
    jobs=dict(zip(chunks[1::2],chunks[2::2]))
    if any(name.startswith('sandium-stage-') for name in jobs):
        raise ValueError('Obsolete Flow jobs must not remain active')
    for stage in range(1,6):
        name=f'full-stage-{stage}'
        if name not in jobs:raise ValueError(f'Missing Full job {name}')
        job=jobs[name]
        if 'feature/sandium-branding-refresh' in job or re.search(r'^    - when:',job,re.M):raise ValueError('Legacy conditional feature wiring')
        blocks=re.findall(r'^    - run:\s*\n(.*?)(?=^    - |\Z)',job,re.M|re.S)
        commands=[]
        for index,block in enumerate(blocks):
            match=re.search(r'^        command: bash (\.circleci/experimental-steps/[A-Za-z0-9_.-]+\.sh)\s*$',block,re.M)
            if match:commands.append((Path(match.group(1)).name,index))
        positions=[]
        for expected in ORDER:
            hits=[i for wrapper,i in commands if wrapper==expected]
            if len(hits)!=1:raise ValueError(f'{name}: expected exactly one direct {expected} invocation')
            positions.append(hits[0])
        if positions!=sorted(positions):raise ValueError(f'{name}: overlay/UI/graph/build order is wrong')
        prepare=[i for i,b in enumerate(blocks) if 'bash .circleci/scripts/prepare-brave-source.sh' in b]
        if len(prepare)!=1 or prepare[0]>=positions[0]:raise ValueError(f'{name}: preparation must precede overlays')
    for wrapper,expected in REQUIRED.items():
        invocations=shell_invocations(repo/'.circleci/experimental-steps'/wrapper)
        names=[name for name,args in invocations]
        for name in names:
            if not (repo/('.circleci/tests' if name == 'test_status_underlap_patch.py' else '.circleci/scripts')/name).is_file():raise ValueError(f'Missing invoked script {name}')
        if names!=expected:raise ValueError(f'{wrapper}: actual apply/test command sequence differs: {names}')
        if wrapper=='product-overlay-25-0.sh' and '--reset-shared' not in invocations[0][1]:raise ValueError('Shared reset must precede feature consumers')
        if wrapper=='product-overlay-29-0.sh':
            for name,args in invocations[:2]:
                for flag in ('--core','--src'):
                    if flag not in args:raise ValueError(f'{name}: missing {flag}')
            if '--repo-root' not in invocations[1][1]:raise ValueError('UI test must inspect the active repository')
            for name,args in invocations[2:4]:
                if '--core' not in args:raise ValueError(f'{name}: missing --core')
            if '--report' not in invocations[2][1]:raise ValueError('Final branding must export coverage report')
            if invocations[4][1] != ['$CORE']:raise ValueError('Native theme must target restored core')
            if invocations[5][1]:raise ValueError('Native theme tests take no arguments')
            if invocations[6][1] != ['$SRC']:raise ValueError('Status trial must target restored Chromium source')
            if invocations[8][1] != ['$CORE']:raise ValueError('Apply popup must target restored core')
            if invocations[9][1] != ['--core', '$CORE']:raise ValueError('Test popup must target restored core')
            if invocations[7][1]:raise ValueError('Status trial tests take no arguments')
    return list(jobs)
