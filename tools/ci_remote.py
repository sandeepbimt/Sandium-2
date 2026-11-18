"""RawS adapter for the established Full-mode Siso/BuildBuddy contract.

Uses the pinned Chromium configurator/backend, never a generic worker image.
No credential value is persisted in source, artifacts or checkpoints.
"""
import ast
import json
import os
from pathlib import Path
import shlex
import subprocess
import selectors
import sys
import time
import codecs

ADDRESS = 'remote.buildbuddy.io:443'
INSTANCE = 'default'
LIMITS = 'local=8,remote=80'
SMOKE_TARGET = 'clang_x64/gen/third_party/perfetto/protos/perfetto/config/priority_boost/priority_boost_config.gen.h'
HELPER_SOURCE = '''#!/usr/bin/env python3
import json, os, sys
if len(sys.argv) != 2 or sys.argv[1] != "get":
    raise SystemExit(1)
sys.stdin.read()
print(json.dumps({"headers": {"x-buildbuddy-api-key": [os.environ["BUILDBUDDY_API_KEY"]]}}))
'''


class StreamRedactor:
    """Hold a suffix so even credentials split across reads cannot escape."""
    def __init__(self, env):
        self.secrets=sorted({str(v) for k,v in env.items() if v and
            any(word in k.upper() for word in ('TOKEN','SECRET','PASSWORD','API_KEY','CREDENTIAL'))},key=len,reverse=True)
        self.keep=max((len(v) for v in self.secrets),default=1)-1
        self.pending=''
    def feed(self,text,final=False):
        self.pending+=text
        cutoff=len(self.pending) if final else max(0,len(self.pending)-self.keep)
        # Avoid emitting a prefix of any known secret crossing the cutoff.
        for secret in self.secrets:
            start=0
            while True:
                start=self.pending.find(secret,start)
                if start<0:break
                if start<cutoff<start+len(secret):cutoff=start
                start+=len(secret)
        ready,self.pending=self.pending[:cutoff],self.pending[cutoff:]
        for secret in self.secrets:ready=ready.replace(secret,'[REDACTED]')
        return ready


def run_logged(command, log_path, *, phase, cwd=None, env=None, check=False,
               append=False, heartbeat_seconds=30):
    """Tee sanitized output without changing timeout arguments or return codes.

    Never prints command arguments or environment. The caller's GNU timeout
    remains the process supervisor; stdin/process-group inheritance is unchanged.
    """
    if heartbeat_seconds<=0:raise ValueError('Heartbeat interval must be positive')
    env=dict(os.environ if env is None else env)
    redactor=StreamRedactor(env)
    decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
    start=time.monotonic()
    with Path(log_path).open('a' if append else 'w') as logfile:
        def emit(text):
            if text:
                logfile.write(text);logfile.flush()
                sys.stdout.write(text);sys.stdout.flush()
        emit(f'RAWS_PHASE_START phase={phase}\n')
        process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                next_beat=start+heartbeat_seconds
                while selector.get_map():
                    events=selector.select(max(0,next_beat-time.monotonic()))
                    for key,_ in events:
                        data=os.read(key.fileobj.fileno(),65536)
                        if data:emit(redactor.feed(decoder.decode(data)))
                        else:
                            selector.unregister(key.fileobj)
                            emit(redactor.feed(decoder.decode(b'',final=True),final=True))
                    now=time.monotonic()
                    if now>=next_beat:
                        emit(f'\nRAWS_PHASE_HEARTBEAT phase={phase} elapsed_seconds={int(now-start)}\n')
                        next_beat=now+heartbeat_seconds
            # A child may close stdout before it exits; keep the phase visible.
            while process.poll() is None:
                now=time.monotonic()
                if now>=next_beat:
                    emit(f'\nRAWS_PHASE_HEARTBEAT phase={phase} elapsed_seconds={int(now-start)}\n')
                    next_beat=now+heartbeat_seconds
                time.sleep(min(.1,max(.001,next_beat-time.monotonic())))
            code=process.wait()
        except BaseException:
            process.kill();process.wait()
            raise
        finally:
            process.stdout.close()
        emit(f'\nRAWS_PHASE_COMPLETE phase={phase} exit={code} elapsed_seconds={int(time.monotonic()-start)}\n')
    if check and code:raise subprocess.CalledProcessError(code,command)
    return subprocess.CompletedProcess(command,code)


def remote_command(out, metrics, target, budget, *, smoke=False):
    if not 1 <= budget <= 1500:
        raise ValueError('Remote slice must fit the 25-minute cap')
    cmd = ['timeout', '--signal=INT', '--kill-after=60s', f'{budget}s',
           'autoninja', '-strict_remote', '-metrics_json', metrics,
           '-C', str(out), '-j80']
    if smoke:
        cmd.append('-re_cache_enable_read=false')
    return cmd + [target]


def configure_rc(text):
    lines = text.splitlines()
    indexes = [i for i, line in enumerate(lines)
               if line.strip() and not line.lstrip().startswith('#')
               and shlex.split(line)[0] == 'ninja']
    if len(indexes) != 1:
        raise ValueError('Expected exactly one native Siso ninja command')
    i = indexes[0]
    tokens = shlex.split(lines[i])
    # Retain upstream flags. Change only these explicit Full-mode settings.
    for name, value in [('-config', 'googlechrome,remote-link'),
                        ('-fs_min_flush_timeout', '300s'),
                        ('-reapi_byte_stream_read_threshold', '1024')]:
        positions = [j for j, token in enumerate(tokens) if token == name]
        if len(positions) > 1:
            raise ValueError(f'Duplicate Siso option: {name}')
        if positions:
            j = positions[0]
            if j + 1 == len(tokens):
                raise ValueError(f'Missing Siso option value: {name}')
            if name == '-config':
                configs = tokens[j + 1].split(',')
                for v in value.split(','):
                    if v not in configs:
                        configs.append(v)
                tokens[j + 1] = ','.join(configs)
            else:
                tokens[j + 1] = value
        else:
            tokens += [name, value]
    tokens = [t for t in tokens if not t.startswith('-re_cache_enable_write=')]
    for flag in ['-reapi_keep_exec_stream', '-re_cache_enable_write=true']:
        if flag not in tokens:
            tokens.append(flag)
    lines[i] = shlex.join(tokens)
    return '\n'.join(lines) + '\n'


def configure(src, depot, env):
    if not env.get('BUILDBUDDY_API_KEY'):
        raise ValueError('MISSING_REQUIRED_SECRET=BUILDBUDDY_API_KEY')
    folder = src / 'build/config/siso'
    backend = folder / 'backend_config/google.star'
    images = []
    for line in backend.read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and key.strip() == 'container_image':
            images.append(ast.literal_eval(value.strip()))
    if len(images) != 1 or not isinstance(images[0], str) or not images[0].startswith('docker://'):
        raise ValueError('Pinned Chromium backend must specify one Docker worker image')
    # Stable path for cross-worker .sisoenv identity, source contains no secret.
    helper = Path('/tmp/raws-buildbuddy-credential-helper.py')
    if helper.is_symlink():
        raise ValueError('Refusing symlink credential helper')
    helper.write_text(HELPER_SOURCE)
    helper.chmod(0o700)
    env = dict(env, SISO_CREDENTIAL_HELPER=str(helper), SISO_LIMITS=LIMITS,
               SISO_REAPI_ADDRESS=ADDRESS, SISO_REAPI_INSTANCE=INSTANCE)
    subprocess.run(['python3', str(folder/'configure_siso.py'),
                    '--reapi_instance', INSTANCE, '--reapi_address', ADDRESS,
                    '--reapi_backend_config_path', str(backend),
                    '--credential-helper', str(helper)], cwd=src, env=env,
                   check=True, timeout=120)
    rc = folder/'.sisorc'
    rc.write_text(configure_rc(rc.read_text()))
    generated = (folder/'backend_config/backend.star').read_text()
    if images[0] not in generated:
        raise ValueError('Configured backend lost the pinned Chromium worker image')
    settings = (folder/'.sisoenv').read_text().splitlines()
    for line in (f'SISO_REAPI_ADDRESS={ADDRESS}', f'SISO_REAPI_INSTANCE={INSTANCE}',
                 f'SISO_CREDENTIAL_HELPER={helper}'):
        if line not in settings:
            raise ValueError('Generated Siso configuration mismatch')
    if not os.access(depot/'autoninja', os.X_OK):
        raise ValueError('Pinned depot_tools/autoninja unavailable')
    return env, {'address': ADDRESS, 'instance': INSTANCE,
                 'worker_image': images[0], 'limits': LIMITS, 'strict_remote': True}


def audit(path, *, require_fresh=False):
    """Full-mode metrics gates; local utility actions are legal, local C++ is not."""
    counts = dict(actions=0, fresh_remote=0, remote_cache_hits=0, local=0)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing remote execution metrics')
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not row.get('step_id'):
            continue
        counts['actions'] += 1
        if any(row.get(k) is True for k in ('err', 'scandeps_err', 'deps_log_err')):
            raise ValueError('Siso reports failed action')
        remote = row.get('is_remote') is True
        cached = row.get('cached') is True
        if row.get('action') in ('cc', 'cxx', 'solink', 'link') and not remote and not cached:
            raise ValueError('Compile/link action executed without remote execution')
        if remote:
            counts['remote_cache_hits' if cached else 'fresh_remote'] += int(cached or row.get('no_exec') is not True)
        elif row.get('is_local') is True:
            counts['local'] += 1
    if not counts['actions'] or (require_fresh and not counts['fresh_remote']):
        raise ValueError('No verified remote worker execution')
    return counts


def smoke(src, out, env, artifacts, stage, seconds):
    metrics = f'raws-stage-{stage}-smoke.jsonl'
    (out/metrics).unlink(missing_ok=True)
    target = out / SMOKE_TARGET
    target.unlink(missing_ok=True)
    run_logged(remote_command(out, metrics, SMOKE_TARGET, min(600, seconds), smoke=True),
               artifacts/f'remote-smoke-{stage}.log', phase=f'remote-smoke-{stage}',
               cwd=src, env=env, check=True)
    if not target.is_file() or not target.stat().st_size:
        raise ValueError('Remote smoke completed without expected generated header')
    return audit(out/metrics, require_fresh=True)
