#!/usr/bin/env python3
import pathlib,json,hashlib,urllib.request
HERE=pathlib.Path(__file__).resolve().parent
REPO=HERE.parents[3]
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
for name,digest in json.loads((HERE/'native-sha256.json').read_text()).items():
 data=urllib.request.urlopen(f'https://raw.githubusercontent.com/chromium/chromium/{PIN}/{name}',timeout=45).read()
 if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Pinned hash mismatch: '+name)
 target=REPO/'native-pinned'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 print(name)
