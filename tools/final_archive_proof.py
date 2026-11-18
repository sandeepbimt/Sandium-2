"""Read a precise APK member from the remotely restored full shard set."""
import hashlib,subprocess,tempfile
from pathlib import PurePosixPath
APK_MEMBER='work/source/src/out/RawSandium/apks/ChromePublic.apk'
def verify_archived_apk(manifest,shards,digest,timeout):
    target=PurePosixPath(APK_MEMBER)
    candidates=[]
    for shard in manifest['shards']:
        for root in shard['root_paths']:
            p=PurePosixPath(root)
            if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive root')
            if p==target or p in target.parents:
                candidates.append(shard);break
    if len(candidates)!=1:raise ValueError('APK must belong to exactly one archive shard')
    shard=candidates[0];name=shard['name']
    if PurePosixPath(name).name!=name:raise ValueError('Unsafe shard name')
    with tempfile.TemporaryFile() as out:
        subprocess.run(['tar','--use-compress-program=zstd','-xOf',str(shards/name),APK_MEMBER],stdout=out,stderr=subprocess.PIPE,check=True,timeout=timeout)
        size=out.tell();out.seek(0)
        actual=hashlib.file_digest(out,'sha256').hexdigest()
    if not size or actual!=digest:raise ValueError('Archived APK digest mismatch')
    return {'member':APK_MEMBER,'shard':name,'sha256':actual,'bytes':size,'proof':'extracted exact APK from remotely restored shard'}
