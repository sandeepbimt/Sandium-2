"""Check exact preimages, applying and reversing the patch without running Chromium."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

kit=Path(__file__).resolve().parent
pins=json.loads((kit/'pins.json').read_text())
source=Path(sys.argv[1]).resolve()
digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
with tempfile.TemporaryDirectory() as work:
    work=Path(work)
    for name, pair in pins.items():
        src=source/name
        assert digest(src)==pair['before'], f"preimage drift: {name}"
        if src.is_file():
            (work/name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src,work/name)
    cmd=['git','apply','--whitespace=error',str(kit/'pinned-ubo.patch')]
    subprocess.run(cmd,cwd=work,check=True)
    for name,pair in pins.items():
        assert digest(work/name)==pair['after'], f"postimage drift: {name}"
    from base64 import b64decode
    import re
    header=(work/'extensions/browser/raws_pinned_ubo.h').read_text()
    spki=''.join(re.findall(r'"([A-Za-z0-9+/=]+)"',header.split('kSigningPublicKey[] =',1)[1].split(';',1)[0]))
    assert hashlib.sha256(b64decode(spki)).hexdigest()=='5a6a81097514fb940453d5d46329eca78100e3cc0c5fca508e1a413f77f567bf'
    harness=work/'identity.cc'
    harness.write_text(r'''#include "extensions/browser/raws_pinned_ubo.h"
using namespace extensions::raws_pinned_ubo;
static_assert(IsPinnedManifest(2,true,kExtensionId,kVersion,kSigningPublicKey));
static_assert(!IsPinnedManifest(3,true,kExtensionId,kVersion,kSigningPublicKey));
static_assert(!IsPinnedManifest(2,false,kExtensionId,kVersion,kSigningPublicKey));
static_assert(!IsPinnedManifest(2,true,"cjpalhdlnbpafiamejdnhcphjbhaame",kVersion,kSigningPublicKey));
static_assert(!IsPinnedManifest(2,true,kExtensionId,"1.76.0",kSigningPublicKey));
static_assert(!IsPinnedManifest(2,true,kExtensionId,kVersion,"different public key"));
int main() {}
''')
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',
                    '-fsyntax-only',str(harness)],cwd=work,check=True)
    subprocess.run(cmd[:2]+['--reverse']+cmd[2:],cwd=work,check=True)
    for name,pair in pins.items():
        assert digest(work/name)==pair['before'], f"reverse drift: {name}"
print('PASS: exact patch apply and reverse; compiled pinned identity assertions and publisher key match.')
