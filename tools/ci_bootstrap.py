#!/usr/bin/env python3
"""Bounded, independent Git verification; no Brave caches or compilation."""
import json, os, subprocess, time
from pathlib import Path
from raw import ROOT, lock, workspace
from source_blob import version_blob

def command(args, timeout=90):
    attempts=[]
    print('Starting:', ' '.join(args), flush=True)
    for attempt in range(2):
        try:
            p=subprocess.run(args,text=True,capture_output=True,timeout=timeout,
                env=dict(os.environ,GIT_TERMINAL_PROMPT='0'))
            item={'returncode':p.returncode,'stdout':p.stdout[-4096:],'stderr':p.stderr[-2048:]}
        except subprocess.TimeoutExpired:
            item={'error':'timeout','seconds':timeout}
        attempts.append(item)
        print('Attempt', attempt+1, 'finished:', item.get('returncode',item.get('error')), flush=True)
        if item.get('returncode')==0:return item['stdout'],attempts
        if attempt==0:time.sleep(3)
    return None,attempts

def tag_matches(output, version, revision):
    if not output:return False
    refs=dict((line.split()[1],line.split()[0]) for line in output.splitlines() if len(line.split())==2)
    tag='refs/tags/'+version
    return refs.get(tag+'^{}',refs.get(tag))==revision

def bootstrap():
    if os.environ.get('CIRCLE_BRANCH')!='raw-sandium/official158':raise ValueError('Wrong branch')
    data=lock(); result={'compilation_attempted':False,'apk_produced':False,'checkpoint_used':False,'steps':{}}
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    try:
        c=data['chromium'];tag='refs/tags/'+c['version']
        text,attempts=command(['git','ls-remote',c['repository'],tag,tag+'^{}'])
        result['steps']['canonical_tag']=attempts
        if not tag_matches(text,c['version'],c['revision']):raise ValueError('Canonical tag not verified against locked SHA; no checkout attempted')
        w=workspace(ROOT/'work/git-bootstrap')
        for name,entry in [('depot_tools',data['depot_tools']),('src',c)]:
            dest=w/name
            if not dest.exists():
                dest.mkdir();subprocess.run(['git','init',str(dest)],check=True,capture_output=True)
            # Name the promisor remote so a filtered fetch can retrieve VERSION later.
            subprocess.run(['git','-C',str(dest),'config','remote.origin.url',entry['repository']],check=True)
            subprocess.run(['git','-C',str(dest),'config','remote.origin.promisor','true'],check=True)
            subprocess.run(['git','-C',str(dest),'config','remote.origin.partialclonefilter','blob:none'],check=True)
            # Fetch only one pinned commit. No checkout, dependencies, hooks, or old caches.
            text,attempts=command(['git','-C',str(dest),'-c','http.lowSpeedLimit=1000','-c','http.lowSpeedTime=30','fetch','--depth=1','--filter=blob:none','--no-tags','origin',entry['revision']],timeout=180)
            result['steps'][name+'_fetch']=attempts
            if text is None:raise ValueError(name+' pinned fetch failed')
            actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','FETCH_HEAD'],text=True).strip()
            if actual!=entry['revision']:raise ValueError(name+' SHA mismatch')
        tree,attempts=command(['git','-C',str(w/'src'),'ls-tree',c['revision'],'chrome/VERSION'])
        result['steps']['git_version_tree']=attempts
        if tree is None:raise ValueError('Pinned Git tree retrieval failed')
        fields=tree.split()
        if len(fields)!=4 or fields[1]!='blob' or fields[3]!='chrome/VERSION':raise ValueError('Unexpected VERSION tree entry')
        text,attempts=version_blob(c['revision'],fields[2])
        result['steps']['verified_version_blob']=attempts
        if text is None:raise ValueError('Checksum-verified VERSION retrieval failed')
        values=dict(line.split('=',1) for line in text.splitlines())
        if '.'.join(values[k] for k in ('MAJOR','MINOR','BUILD','PATCH'))!=c['version']:raise ValueError('VERSION mismatch')
        result['source_provenance_verified']=True
        result['next_step']='Separate dependency sync and hooks; full compile not yet attempted'
        return 0
    except (ValueError,subprocess.SubprocessError) as e:
        result['blocker']=str(e);result['source_provenance_verified']=False
        return 1
    finally:
        (out/'git-bootstrap.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
if __name__=='__main__':raise SystemExit(bootstrap())
