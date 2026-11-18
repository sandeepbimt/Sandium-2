"""Real subprocess callbacks for baseline_seed.transition; no transport or CI actions.

The baseline imports ONLY the unchanged reviewed checkout. Commands/proofs are
emitted by actual subprocess execution; unit-test mocks are not service evidence.
"""
import json
import os
import math
import signal
import time
from pathlib import Path
import subprocess
import sys

from baseline_seed import BASELINE_COMMIT, BASELINE_FINGERPRINT, RECEIPT

# -I prevents ambient PYTHONPATH/current-directory imports. Arguments are local
# reviewed checkout paths, never commands taken from downloaded receipts.
_CHILD = r'''
import hashlib,json,os,subprocess,sys
from pathlib import Path
checkout,root,phase,expected_commit,old_fingerprint,receipt_id,requested = sys.argv[1:]
checkout,root=Path(checkout).resolve(),Path(root).resolve()
artifacts=root/'artifacts/feature-seed';artifacts.mkdir(parents=True,exist_ok=True)
journal=artifacts/(phase+'-commands.jsonl')
def audit(event,args):
    if event=='subprocess.Popen':
        # Deliberately never log environment: it may contain build credentials.
        with journal.open('a') as f:
            f.write(json.dumps({'argv':args[1],'cwd':str(args[2]) if args[2] else None},default=str)+'\n')
sys.addaudithook(audit)
def git(*args):
    return subprocess.check_output(['git','-C',str(checkout),*args],text=True,timeout=60).strip()
if phase=='baseline':
    if git('rev-parse','HEAD')!=expected_commit:raise ValueError('Wrong baseline checkout commit')
    if git('status','--porcelain','--untracked-files=no'):raise ValueError('Modified baseline checkout')
    # Untracked executable/import inputs could shadow the reviewed baseline.
    if git('ls-files','--others','--exclude-standard','--','tools','.circleci'):
        raise ValueError('Foreign baseline implementation files')
sys.path.insert(0,str(checkout/'tools'))
from raw import lock,verify
from ci_compile import fingerprint
from ci_official import verify_official
from ci_remote import verify_graph_outputs
actual_fingerprint=fingerprint()
workspace=root/'work/source';src=workspace/'src';depot=workspace/'depot_tools';out=src/'out/RawSandium'
data=lock()
env=dict(os.environ,PATH=str(depot)+os.pathsep+os.environ.get('PATH',''),DEPOT_TOOLS_UPDATE='0')
def tool_pin():
    actual=subprocess.check_output(['git','-C',str(depot),'rev-parse','HEAD'],text=True,timeout=60).strip()
    if actual!=data['depot_tools']['revision']:raise ValueError('Wrong depot_tools revision')
    if subprocess.check_output(['git','-C',str(depot),'diff','HEAD','--name-only'],text=True,timeout=60).strip():
        raise ValueError('Modified tracked depot_tools source')
    if not os.access(depot/'gn',os.X_OK):raise ValueError('Pinned GN unavailable')
def official(stage):
    if (out/'args.gn').read_bytes()!=(checkout/'ci/args.gn').read_bytes():raise ValueError('GN args differ from selected recipe')
    result=verify_official(src,depot,out,env,artifacts,stage)
    verify_graph_outputs(src,depot,out,env,artifacts,stage)
    return result
result={'phase':phase,'fingerprint':actual_fingerprint,'baseline_receipt':receipt_id}
if phase=='baseline':
    if actual_fingerprint!=old_fingerprint:raise ValueError('Baseline fingerprint mismatch')
    sys.path.insert(0,str(checkout/'.circleci/bridge'))
    from cli import quiesce
    quiesce(checkout/'.circleci/scripts/sandium-checkpoint-shards.py',workspace)
    verify(src,data)
    tool_pin()
    result['official']=official('seed-baseline')
else:
    from native_features import load_manifest,apply,verify_applied
    if not load_manifest(checkout):raise ValueError('Feature seed requires nonempty explicit opt-in')
    admission=json.loads((root/'.baseline-seed/admission.json').read_text())
    if (admission.get('status')!='transitioning' or admission.get('baseline_receipt')!=receipt_id
            or admission.get('baseline_fingerprint')!=old_fingerprint
            or admission.get('feature_fingerprint')!=actual_fingerprint
            or actual_fingerprint==old_fingerprint):raise ValueError('Wrong active seed transition')
    if phase=='verify' and requested!=actual_fingerprint:raise ValueError('Requested feature fingerprint changed')
    tool_pin()
    if phase=='apply':
        verify(src,data,allow_feature_preimages=True)
        apply(src,checkout)
        verify(src,data)
    elif phase=='gn':
        verify(src,data)
        out.mkdir(parents=True,exist_ok=True)
        (out/'args.gn').write_bytes((checkout/'ci/args.gn').read_bytes())
        subprocess.run([str(depot/'gn'),'gen','out/RawSandium','--fail-on-unused-args'],
                       cwd=src,env=env,check=True,timeout=300)
        if not (out/'build.ninja').is_file():raise ValueError('GN failed to produce graph')
        verify(src,data)
    elif phase=='verify':
        verify(src,data)
        result['official']=official('seed-feature')
    else:raise ValueError('Unknown seed callback phase')
    result['feature_postimages']=verify_applied(src,checkout).hashes
# Receipt is emitted only after the real phase completes successfully.
print('FEATURE_SEED_PHASE_PROOF='+json.dumps(result,sort_keys=True))
'''


JOB_LIMIT_SECONDS = 3300
POST_TRANSITION_RESERVE = 1620
CLEANUP_RESERVE = 50  # phase TERM/KILL grace + quiescence + its TERM/KILL grace
QUIESCENCE_TIMEOUT = 30
PHASE_LIMITS = {'baseline': 180, 'apply': 120, 'gn': 330, 'verify': 180}


def run_owned(command, *, env, cwd, timeout, grace=5):
    """Own the entire process group, including grandchildren on failure/timeout."""
    process = subprocess.Popen(command, env=env, cwd=cwd, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except BaseException as error:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=grace)
        except subprocess.TimeoutExpired:
            stdout, stderr = '', ''
        finally:
            # The leader can exit while a detached-from-pipes descendant still
            # owns a workspace FD. Kill the group even when communicate returned.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        final_out, final_err = process.communicate(timeout=grace)
        if isinstance(error, (subprocess.TimeoutExpired, subprocess.CalledProcessError)):
            error.stdout, error.stderr = final_out or stdout, final_err or stderr
        raise


_QUIESCE = r'''
import subprocess,sys
from pathlib import Path
checkout,root,revision=map(str,sys.argv[1:])
checkout=Path(checkout);root=Path(root)
if subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True,timeout=10).strip()!=revision:
    raise ValueError('Wrong cleanup baseline checkout')
if subprocess.check_output(['git','-C',str(checkout),'status','--porcelain','--untracked-files=no'],text=True,timeout=10).strip():
    raise ValueError('Modified cleanup baseline checkout')
if subprocess.check_output(['git','-C',str(checkout),'ls-files','--others','--exclude-standard','--','tools','.circleci'],text=True,timeout=10).strip():
    raise ValueError('Foreign cleanup baseline implementation files')
sys.path.insert(0,str(checkout/'.circleci/bridge'))
from cli import quiesce
quiesce(checkout/'.circleci/scripts/sandium-checkpoint-shards.py',root/'work/source')
'''


class SeedCallbacks:
    def __init__(self, recipe_root, baseline_checkout, *, env=None):
        self.recipe_root = Path(recipe_root).resolve()
        self.baseline_checkout = Path(baseline_checkout).resolve()
        if self.recipe_root == self.baseline_checkout:
            raise ValueError('Baseline must use a separate unchanged checkout')
        from native_features import load_manifest
        if not load_manifest(self.recipe_root):
            raise ValueError('Feature seed requires nonempty explicit opt-in')
        self.env = dict(os.environ if env is None else env)
        try:
            self.job_started = float(self.env['RAWS_FEATURE_JOB_STARTED_EPOCH'])
        except (KeyError, ValueError):
            raise ValueError('Original feature job start epoch required') from None
        if not math.isfinite(self.job_started) or self.job_started <= 0 or self.job_started > time.time() + 5:
            raise ValueError('Invalid original feature job start epoch')
        self.started_monotonic = time.monotonic()
        self.initial_elapsed = max(0, time.time() - self.job_started)
        self._root = None
        self._phase = 'baseline'

    def callbacks(self):
        return {name: getattr(self, name) for name in (
            'verify_baseline', 'apply_features', 'generate_gn', 'verify_features')}

    def _remaining(self):
        elapsed = max(time.time() - self.job_started,
                      self.initial_elapsed + time.monotonic() - self.started_monotonic)
        return JOB_LIMIT_SECONDS - elapsed

    def _timeout(self, phase):
        available = self._remaining() - POST_TRANSITION_RESERVE - CLEANUP_RESERVE
        minimum = 30 if phase == 'apply' else 60
        if available < minimum:
            raise ValueError('Insufficient original job budget for seed ' + phase)
        return min(PHASE_LIMITS[phase], available)

    def _cleanup(self, root, artifacts):
        command = [sys.executable, '-I', '-c', _QUIESCE, str(self.baseline_checkout),
                   str(root), BASELINE_COMMIT]
        timeout = min(QUIESCENCE_TIMEOUT, self._remaining() - 10)
        if timeout < 1:
            raise ValueError('No original job budget for quiescence confirmation')
        (artifacts / 'failure-quiescence-invocation.json').write_text(json.dumps(command, indent=2)+'\n')
        result = run_owned(command, env=self.env, cwd=self.baseline_checkout, timeout=timeout)
        (artifacts / 'failure-quiescence.log').write_text(result.stdout + result.stderr)

    def _run(self, root, phase, requested=''):
        root = Path(root).resolve()
        if phase != self._phase or (self._root is not None and root != self._root):
            raise ValueError('Seed callback order/root mismatch')
        timeout = self._timeout(phase)
        checkout = self.baseline_checkout if phase == 'baseline' else self.recipe_root
        artifacts = root / 'artifacts/feature-seed'
        artifacts.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-I', '-c', _CHILD, str(checkout), str(root), phase,
                   BASELINE_COMMIT, BASELINE_FINGERPRINT, RECEIPT, requested]
        # Record the real invocation, not an assertion that it succeeded.
        (artifacts / (phase + '-invocation.json')).write_text(json.dumps(command, indent=2)+'\n')
        (artifacts / (phase + '-budget.json')).write_text(json.dumps({
            'original_job_started_epoch':self.job_started, 'phase_timeout_seconds':timeout,
            'remaining_seconds':self._remaining(), 'post_transition_reserve_seconds':POST_TRANSITION_RESERVE,
            'cleanup_reserve_seconds':CLEANUP_RESERVE}, indent=2)+'\n')
        try:
            completed = run_owned(command, env=self.env, cwd=checkout, timeout=timeout)
        except BaseException as error:
            def text(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
            (artifacts / (phase + '-stdout.log')).write_text(text(getattr(error, 'stdout', '')))
            (artifacts / (phase + '-stderr.log')).write_text(text(getattr(error, 'stderr', '')))
            try:
                self._cleanup(root, artifacts)
            except BaseException as cleanup_error:
                (artifacts / 'failure-quiescence-error.txt').write_text(str(cleanup_error))
                raise ValueError('Seed phase failed and quiescence could not be confirmed') from error
            raise
        (artifacts / (phase + '-stdout.log')).write_text(completed.stdout)
        (artifacts / (phase + '-stderr.log')).write_text(completed.stderr)
        lines = [line.split('=', 1)[1] for line in completed.stdout.splitlines()
                 if line.startswith('FEATURE_SEED_PHASE_PROOF=')]
        if len(lines) != 1:
            raise ValueError('Missing unique actual subprocess phase proof')
        result = json.loads(lines[0])
        if result.get('phase') != phase or result.get('baseline_receipt') != RECEIPT:
            raise ValueError('Wrong subprocess phase proof')
        (artifacts / (phase + '-proof.json')).write_text(json.dumps(result, indent=2)+'\n')
        self._root = root
        self._phase = {'baseline':'apply', 'apply':'gn', 'gn':'verify', 'verify':'complete'}[phase]
        return result

    def verify_baseline(self, root, receipt):
        if receipt.get('id') != RECEIPT:
            raise ValueError('Unreviewed baseline receipt')
        return self._run(root, 'baseline')

    def apply_features(self, root):
        return self._run(root, 'apply')

    def generate_gn(self, root):
        return self._run(root, 'gn')

    def verify_features(self, root, new_fingerprint):
        return self._run(root, 'verify', new_fingerprint)
