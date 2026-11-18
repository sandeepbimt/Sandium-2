#!/usr/bin/env python3
"""Fast source packing only when a compiler slice needs continuation."""
import argparse,json,subprocess,tarfile
from raw import ROOT
from ci_compile import file_sha

def main(action):
    hand=ROOT/'handoff/source';archive=hand/'source.tar.zst'
    if action=='pack':
        state=json.loads((ROOT/'handoff/stage1/state.json').read_text())
        if state['status']!='slice_expired':return
        hand.mkdir(parents=True,exist_ok=True)
        subprocess.run(['tar','--use-compress-program=zstd -T4 -1','--exclude=source/src/out','-cf',str(archive),'-C',str(ROOT/'work'),'source'],check=True,timeout=600)
        (hand/'receipt.json').write_text(json.dumps({'sha256':file_sha(archive),'fingerprint':state['fingerprint']}))
    else:
        from ci_compile import fingerprint
        receipt=json.loads((hand/'receipt.json').read_text())
        if receipt['fingerprint']!=fingerprint() or file_sha(archive)!=receipt['sha256']:raise ValueError('Foreign or corrupt source handoff')
        dest=ROOT/'work';dest.mkdir(exist_ok=True)
        if (dest/'source').exists():raise ValueError('Refusing existing source restore')
        # Data extraction filter rejects escaping links, absolute paths and devices.
        with subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE) as proc:
            with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:tar.extractall(dest,filter='data')
            if proc.wait():raise ValueError('Source decompression failed')
        archive.unlink() # Local copy only; workflow workspace is unchanged.
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','restore']);main(p.parse_args().action)
