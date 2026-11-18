"""Read pinned Chromium VERSION over independent HTTPS routes, verify Git blob hash."""
import base64, hashlib, json, urllib.request

def blob_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def decode_verified(body, route, expected):
    if route=='canonical_gitiles':
        data=base64.b64decode(body.strip(),validate=True)
    else:
        obj=json.loads(body)
        if obj.get('sha')!=expected or obj.get('encoding')!='base64':raise ValueError('Mirror metadata mismatch')
        data=base64.b64decode(''.join(obj['content'].split()),validate=True)
    if blob_sha(data)!=expected:raise ValueError('Source blob checksum mismatch')
    return data

def version_blob(revision, expected):
    routes=[('canonical_gitiles','https://chromium.googlesource.com/chromium/src.git/+/'+revision+'/chrome/VERSION?format=TEXT'),
            ('official_github_mirror','https://api.github.com/repos/chromium/chromium/contents/chrome/VERSION?ref='+revision)]
    attempts=[]
    for name,url in routes:
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Raw-Sandium-source-verifier'}),timeout=30) as r:
                body=r.read(65537)
                if len(body)>65536:raise ValueError('Oversized source response')
                data=decode_verified(body,name,expected)
            attempts.append({'route':name,'verified':True,'blob_sha':expected})
            return data.decode(),attempts
        except Exception as e:
            attempts.append({'route':name,'verified':False,'error':type(e).__name__,'status':getattr(e,'code',None)})
    return None,attempts
