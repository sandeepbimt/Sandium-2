"""Recipe identity covers target/toolchain/GN, all patches and feature assets."""
import hashlib,subprocess
from pathlib import Path

def fingerprint(root):
 root=Path(root)
 files=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
 if not files:raise ValueError('missing tracked recipe')
 h=hashlib.sha256()
 for name in sorted(files):
  path=root/name
  if path.is_symlink():raise ValueError('recipe symlink not admitted')
  if path.is_file():h.update(name.encode()+b'\0'+path.read_bytes()+b'\0')
  elif path.is_dir():
   # Gitlinks are identity-bearing even though their files are not listed.
   entry=subprocess.check_output(['git','ls-files','--stage','--',name],cwd=root)
   h.update(name.encode()+b'\0'+entry+b'\0')
  else:raise ValueError('missing tracked recipe input '+name)
 return h.hexdigest()
