"""Run a build process group; only this supervisor may attest budget expiry."""
import argparse,json,os,pathlib,signal,subprocess,time

def run(seconds, marker, command, grace=60):
    marker.unlink(missing_ok=True)
    proc=subprocess.Popen(command,start_new_session=True)
    def kill_surviving_group():
        # The leader may exit before an interrupt-ignoring descendant. Do not
        # permit handoff while a surviving compiler can still mutate outputs.
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    def interrupted(sig, frame):
        try: os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
        kill_surviving_group()
        raise SystemExit(128+sig)
    for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, interrupted)
    expired=False
    try:
        rc=proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        expired=True
        try: os.killpg(proc.pid,signal.SIGINT)
        except ProcessLookupError: pass
        try: proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
        kill_surviving_group()
        rc=124
    marker.write_text(json.dumps({'budget_expired':expired,'exit_code':rc})+'\n')
    return rc if rc>=0 else 128-rc

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,required=True);p.add_argument('--marker',type=pathlib.Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args(); command=a.command[1:] if a.command[:1]==['--'] else a.command
    if a.seconds<=0 or not command:p.error('positive budget and command required')
    raise SystemExit(run(a.seconds,a.marker,command))
