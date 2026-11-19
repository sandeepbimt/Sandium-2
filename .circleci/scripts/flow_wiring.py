"""Validate active Full-only pipeline's generated YAML subset and actual overlay shell commands.

This intentionally accepts only direct run-command wrappers used by Full, not a
partial general YAML interpreter. Unknown/conditional wiring fails closed. No
PyYAML dependency is introduced into build-stage Python.
"""
from pathlib import Path
import re
import shlex

ORDER = [f'product-overlay-{i}-0.sh' for i in range(24,31)] + ['graph-validation.sh','remote-smoke.sh','full-bounded-build.sh']
REQUIRED = {
 'product-overlay-30-0.sh': ['test-sandium-removal-composition.py','apply-sandium-native-insets.py','sandium-removal-recipe.py','apply-sandium-home-shortcuts.py','apply-sandium-home-shortcuts.py','apply-sandium-video-gestures.py','apply-sandium-video-gestures.py','apply-sandium-dark-combined.py','apply-sandium-dark-combined.py','test-sandium-dark-composition.py','.circleci/features/page-text/apply.py','.circleci/features/page-text/apply.py','.circleci/features/page-text/tests/test_combined.py','apply-sandium-homepage-combined.py','apply-sandium-homepage-combined.py','apply-sandium-capture-coherence.py','apply-sandium-capture-coherence.py','apply-sandium-address-progress.py','apply-sandium-address-progress.py','test-sandium-address-progress.py','apply-sandium-native-insets.py','.circleci/features/page-text/apply.py','precheck-graph.py','removal-evidence.py'],
 'product-overlay-24-0.sh': ['apply-sandium-branding.sh'],
 'product-overlay-25-0.sh': ['apply-sandium-adblock-engine-race.py','apply-sandium-filter-subscriptions.py','apply-sandium-filter-bootstrap.py'],
 'product-overlay-26-0.sh': ['apply-sandium-page-transition-full.py','apply-sandium-back-transition.py','apply-sandium-back-controls.py','trace-sandium-back-geometry.py'],
 'product-overlay-27-0.sh': ['apply-sandium-homepage-adblock-warmup.py','apply-sandium-download-concurrency.py','apply-sandium-welcome-setup.py','apply-sandium-deferred-notifications.py','test-sandium-homepage-adblock-warmup.py','test-sandium-download-concurrency.py','test-sandium-welcome-setup.py','test-sandium-page-transition-full.py','verify-sandium-vanilla-brave.py'],
 'product-overlay-28-0.sh': ['apply-sandium-shields-two-state.py','apply-sandium-adblock-engine-race.py','test-sandium-shields-two-state.py','test-sandium-adblock-engine-race.py','test-sandium-filter-subscriptions.py','test-sandium-filter-bootstrap.py','apply-sandium-adblock-resources.py','test-sandium-adblock-resources.py'],
 'product-overlay-29-0.sh': ['apply-sandium-ui-prune.py','test-sandium-ui-prune.py','apply-sandium-no-video-promo.py','apply-sandium-visible-branding.py','test-sandium-visible-branding.py','apply-sandium-native-theme.py','test-sandium-native-theme.py','apply-sandium-native-insets.py','apply-sandium-native-insets.py','apply-sandium-shields-popup.py','test-sandium-shields-popup.py','apply-sandium-bottom-toolbar.py','test-sandium-bottom-toolbar.py','apply-sandium-paged-menu.py','apply-sandium-paged-menu.py','apply-sandium-chrome-theme.py','test-sandium-chrome-theme.py','test-sandium-motion.py','apply-sandium-unified-address.py','apply-sandium-unified-address.py','test-sandium-unified-address.py','apply-sandium-toolbar-refinements.py','apply-sandium-toolbar-refinements.py','test-sandium-toolbar-refinements.py','apply-sandium-search-choices.py','apply-sandium-search-choices.py','test-sandium-search-choices.py','apply-sandium-focus-follow.py','apply-sandium-focus-follow.py','test-sandium-focus-follow.py','apply-sandium-settings-fade.py','apply-sandium-settings-fade.py','test-sandium-settings-fade.py','apply-sandium-progress-diagnostics.py','apply-sandium-progress-diagnostics.py','test-sandium-progress-diagnostics.py','apply-sandium-suggestion-anchor.py','apply-sandium-suggestion-anchor.py','test-sandium-suggestion-anchor.py','apply-sandium-ui-links.py','test-sandium-ui-links.py','apply-sandium-oppo-toggles.py','test-sandium-oppo-toggles.py'],
}

NAV='apply-sandium-native-navigation.py'
DIAG='apply-sandium-navigation-diagnostics.py'
for wrapper in REQUIRED:
    REQUIRED[wrapper].insert(0,NAV)
    REQUIRED[wrapper].insert(1,DIAG)
REQUIRED['product-overlay-30-0.sh'][-2:-2]=[DIAG,DIAG,NAV,NAV]
REQUIRED['product-overlay-30-0.sh'].append('apply-sandium-lint-resources.py')
REQUIRED['product-overlay-30-0.sh'].append('apply-sandium-deferred-notifications.py')


# Exact reviewed dispatch: U defers graph audits until its final GN generation.
# This is not permission for arbitrary optional product execution.
FULL_U_GRAPH_DISPATCH = """if [ -n "${FULL_U_SCOPE:-}" ]; then
  echo 'FULL_U_GRAPH_AUDITS=DEFERRED until final official GN generation; no readiness claim'
else
  python3 .circleci/scripts/precheck-graph.py --audits-only
  python3 .circleci/scripts/removal-evidence.py capture --root "$ROOT"
fi"""
FULL_GRAPH_AUDITS = """python3 .circleci/scripts/precheck-graph.py --audits-only
python3 .circleci/scripts/removal-evidence.py capture --root "$ROOT"
"""

FULL_U_SOURCE_DISPATCH = 'if [ -n "${FULL_U_SCOPE:-}" ]; then\n  python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply-source\nelse\n  python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply\nfi'
FULL_SOURCE_APPLY = 'python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply'

FULL_U_BASE_DISPATCH = 'if [ -n "${FULL_U_SCOPE:-}" ]; then\n  python3 .circleci/upgrades/product.py verify-base --root "$ROOT"\nelse\n  python3 .circleci/scripts/verify-sandium-vanilla-brave.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase verify\nfi'
FULL_BASE_VERIFY = 'python3 .circleci/scripts/verify-sandium-vanilla-brave.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase verify'
FULL_U_LINKS_DISPATCH = 'LINKS_PROFILE=legacy156\nif [ -n "${FULL_U_SCOPE:-}" ]; then LINKS_PROFILE=target158; fi\npython3 .circleci/scripts/test-sandium-ui-links.py --core "$CORE" --src "$SRC" --source-profile "$LINKS_PROFILE"'
FULL_LINKS_VERIFY = 'python3 .circleci/scripts/test-sandium-ui-links.py --core "$CORE" --src "$SRC" --source-profile legacy156'

def shell_invocations(path):
    text=path.read_text();result=[];heredoc=None
    if 'FULL_U_SCOPE' in text:
        dispatches={
          'product-overlay-27-0.sh':[(FULL_U_BASE_DISPATCH,FULL_BASE_VERIFY)],
          'product-overlay-29-0.sh':[(FULL_U_LINKS_DISPATCH,FULL_LINKS_VERIFY)],
          'product-overlay-30-0.sh':[(FULL_U_GRAPH_DISPATCH,FULL_GRAPH_AUDITS),(FULL_U_SOURCE_DISPATCH,FULL_SOURCE_APPLY)]}
        pairs=dispatches.get(path.name,[])
        if not pairs or text.count('FULL_U_SCOPE')!=len(pairs) or any(text.count(old)!=1 for old,new in pairs):
            raise ValueError('Unreviewed Full-U typed dispatch')
        for old,new in pairs:text=text.replace(old,new)
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
        if len(tokens)>1 and tokens[0] in ('python3','bash') and tokens[1].startswith(('.circleci/scripts/','$ROOT/.circleci/scripts/','${ROOT}/.circleci/scripts/','.circleci/tests/','.circleci/features/page-text/')):
            if any(t in (';','&&','||','|','&') for t in tokens):raise ValueError('Compound/optional overlay invocation unsupported')
            result.append((tokens[1] if tokens[1].startswith('.circleci/features/page-text/') else Path(tokens[1]).name,tokens[2:]))
    if heredoc:raise ValueError('Unclosed shell heredoc')
    return result


def verify_full_wiring(repo):
    repo=Path(repo);text=(repo/'.circleci/config.yml').read_text()
    if re.search(r'^  brave-android-staged-build:',text,re.M):
        # Original Full has one parameterized job. Accept only the independently
        # reviewed exact config, then retain every product invocation/argument gate.
        import hashlib
        expected=(repo/'.circleci/original-full/config.sha256').read_text().strip()
        if not re.fullmatch('[0-9a-f]{64}',expected) or hashlib.sha256(text.encode()).hexdigest()!=expected:
            raise ValueError('Original Full configuration differs from reviewed wiring')
        verify_product_wrappers(repo)
        return ['brave-android-staged-build','renew-fixed-reference']

    section=re.search(r'^jobs:\s*\n(.*?)(?=^[A-Za-z][A-Za-z0-9_-]*:|\Z)',text,re.M|re.S)
    if not section:raise ValueError('Missing jobs section')
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
    verify_product_wrappers(repo)
    return list(jobs)


def verify_product_wrappers(repo):
    repo=Path(repo)
    for wrapper,expected in REQUIRED.items():
        invocations=shell_invocations(repo/'.circleci/experimental-steps'/wrapper)
        names=[name for name,args in invocations]
        for name in names:
            if name.startswith('.circleci/features/page-text/'):
                if not (repo/name).is_file():raise ValueError(f'Missing invoked script {name}')
                continue
            if not (repo/('.circleci/tests' if name == 'test_status_underlap_patch.py' else '.circleci/scripts')/name).is_file():raise ValueError(f'Missing invoked script {name}')
        if names!=expected:raise ValueError(f'{wrapper}: actual apply/test command sequence differs: {names}')
        if wrapper=='product-overlay-30-0.sh':
            if invocations[-1] != ('apply-sandium-deferred-notifications.py', ['--src','$SRC','--verify-only']):
                raise ValueError('Final notification readback must follow every product mutator')
            invocations=invocations[:-1]
            if invocations[-1] != ('apply-sandium-lint-resources.py',['--core','$CORE']):raise ValueError('Reviewed lint resources must target restored core after product overlays')
            invocations=invocations[:-1]
        if invocations[0] != (NAV,['$CIRCLE_WORKING_DIRECTORY/brave-work/src','--mode','off']):raise ValueError('Native navigation rollback must precede every product mutator')
        if wrapper=='product-overlay-30-0.sh' and invocations[-4:-2] != [(NAV,['$SRC','--mode','configured']),(NAV,['$SRC','--mode','configured','--verify-only'])]:raise ValueError('Native navigation profile must apply and verify after all frozen overlays')
        diag_args=[args for name,args in invocations if name==DIAG]
        expected_diag=[['$CIRCLE_WORKING_DIRECTORY/brave-work/src','--reset-native-probes']]
        if wrapper=='product-overlay-30-0.sh':expected_diag += [['$SRC'],['$SRC','--verify-only']]
        if diag_args!=expected_diag:raise ValueError('Diagnostics require preflight reversal and final apply/readback')
        invocations=[item for item in invocations if item[0] not in (NAV,DIAG)]
        text_calls=[args for name,args in invocations if name.startswith('.circleci/features/page-text/')]
        if wrapper=='product-overlay-30-0.sh' and text_calls != [['$SRC','--repo','$ROOT'],['$SRC','--repo','$ROOT','--verify-only'],[],['$SRC','--repo','$ROOT','--verify-only']]:
            raise ValueError('Page text requires atomic apply, readback and pinned composition test')
        invocations=[item for item in invocations if not item[0].startswith('.circleci/features/page-text/')]
        if wrapper=='product-overlay-30-0.sh' and invocations[0][1] != ['--source','$CORE','--chromium-source','$SRC','--gn','$SRC/buildtools/linux64/gn']:raise ValueError('Composition must read both pinned repositories')
        if wrapper=='product-overlay-30-0.sh':
            if invocations[1][1] != ['$SRC']:raise ValueError('Resumed UI needs native inset migration')
            if invocations[-3][1] != ['$SRC','--verify-only']:raise ValueError('Final native insets require readback')
            if invocations[3][1] != ['$SRC','--repo','$ROOT'] or invocations[4][1] != ['$SRC','--repo','$ROOT','--verify-only']:
                raise ValueError('Home shortcuts must target restored source and verify after removal')
            if invocations[5][1] != ['$SRC','--repo','$ROOT'] or invocations[6][1] != ['$SRC','--repo','$ROOT','--verify-only']:
                raise ValueError('Fullscreen controls require actual-tree verification')
            if invocations[7][1] != ['$SRC','--repo','$ROOT'] or invocations[8][1] != ['$SRC','--repo','$ROOT','--verify-only'] or invocations[9][1]:
                raise ValueError('Dark Pages require pinned combined application, readback and composition tests')
            if invocations[10][1] != ['$SRC'] or invocations[11][1] != ['$SRC','--verify-only']:
                raise ValueError('Homepage backing and paint require combined apply and readback')
        if wrapper=='product-overlay-30-0.sh' and invocations[-2][1] != ['--audits-only']:raise ValueError('Aggregated audits must not repeat preparation')
        if wrapper=='product-overlay-26-0.sh' and invocations[-1][1] != ['$CIRCLE_WORKING_DIRECTORY/brave-work/src','--reset']:raise ValueError('Geometry trace must reset before status overlay')
        if wrapper=='product-overlay-25-0.sh' and '--reset-shared' not in invocations[0][1]:raise ValueError('Shared reset must precede feature consumers')
        if wrapper=='product-overlay-29-0.sh':
            promo=[args for name,args in invocations if name=='apply-sandium-no-video-promo.py']
            if promo != [['--core', '$CORE']]:raise ValueError('Video promo removal must target restored core')
            invocations=[item for item in invocations if item[0]!='apply-sandium-no-video-promo.py']
            for name,args in invocations[:2]:
                for flag in ('--core','--src'):
                    if flag not in args:raise ValueError(f'{name}: missing {flag}')
            if '--repo-root' not in invocations[1][1]:raise ValueError('UI test must inspect the active repository')
            for name,args in invocations[2:4]:
                if '--core' not in args:raise ValueError(f'{name}: missing --core')
            if '--report' not in invocations[2][1]:raise ValueError('Final branding must export coverage report')
            if invocations[4][1] != ['$CORE']:raise ValueError('Native theme must target restored core')
            if invocations[5][1]:raise ValueError('Native theme tests take no arguments')
            if invocations[6][1] != ['$SRC']:raise ValueError('Native insets must target restored Chromium source')
            if invocations[8][1] != ['$CORE']:raise ValueError('Apply popup must target restored core')
            if invocations[9][1] != ['--core', '$CORE']:raise ValueError('Test popup must target restored core')
            if invocations[7][1] != ['$SRC','--verify-only']:raise ValueError('Native insets require source readback')
            for index in (10,11):
                if invocations[index][1] != ['--src', '$SRC', '--core', '$CORE']:
                    raise ValueError('Native toolbar must target restored source/core')
            if invocations[12][1] != ['$SRC','--repo','$ROOT']:
                raise ValueError('Paged menu must target restored source and active repository')
            if invocations[13][1] != ['$SRC','--repo','$ROOT','--verify-only']:
                raise ValueError('Paged menu post-apply verification is required')
            if invocations[14][1] != ['$SRC'] or invocations[15][1]:
                raise ValueError('Chrome theme must target restored source with its contract test')
            if invocations[17][1] != ['--src','$SRC','--core','$CORE'] or invocations[18][1] != ['--src','$SRC','--core','$CORE','--verify-only'] or invocations[19][1]:
                raise ValueError('Unified address requires pinned source/core and readback verification')
            if invocations[20][1] != ['--src','$SRC'] or invocations[21][1] != ['--src','$SRC','--verify-only'] or invocations[22][1]:
                raise ValueError('Toolbar refinements require pinned source and readback')
            if invocations[16][1]:
                raise ValueError('Motion contract takes no external inputs')
            if invocations[23][1] != ['--core','$CORE'] or invocations[24][1] != ['--core','$CORE','--verify-only'] or invocations[25][1]:
                raise ValueError('Search choices require pinned core and readback verification')
            if invocations[26][1] != ['--src','$SRC'] or invocations[27][1] != ['--src','$SRC','--verify-only'] or invocations[28][1]:
                raise ValueError('Focus follow requires pinned source and readback')
            if invocations[29][1] != ['--src','$SRC','--core','$CORE'] or invocations[30][1] != ['--src','$SRC','--core','$CORE','--verify-only'] or invocations[31][1]:
                raise ValueError('Settings fade requires source/core and readback')
            if invocations[32][1] != ['--src','$SRC'] or invocations[33][1] != ['--src','$SRC','--verify-only'] or invocations[34][1]:
                raise ValueError('Progress diagnostics require source and readback')
            if invocations[35][1] != ['$SRC'] or invocations[36][1] != ['$SRC','--verify-only'] or invocations[37][1]:
                raise ValueError('Suggestion grouping requires source and readback')
            for index in (38,39):
                expected=['--core','$CORE','--src','$SRC']
                if index==39 and FULL_U_LINKS_DISPATCH in (repo/'.circleci/experimental-steps'/wrapper).read_text():expected += ['--source-profile','legacy156']
                if invocations[index][1] != expected:
                    raise ValueError('UI links require restored core and source')
            if invocations[40][1] != ['$SRC','$CORE'] or invocations[41][1]:
                raise ValueError('Oppo toggles require restored source/core and contract')
