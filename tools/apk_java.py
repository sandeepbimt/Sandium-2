"""Use Chromium's restored DEPS-managed JDK for pinned SDK APK verification."""
import os,subprocess
from pathlib import Path

def environment(src,env):
    src=Path(src).resolve(strict=True)
    home=(src/'third_party/jdk/current').resolve(strict=True)
    if not home.is_relative_to(src):raise ValueError('Restored JDK escapes verified source tree')
    java=home/'bin/java'
    if not java.is_file() or not os.access(java,os.X_OK):raise ValueError('Pinned restored JDK java is missing or not executable')
    if not java.resolve(strict=True).is_relative_to(home):raise ValueError('Pinned Java executable escapes restored JDK')
    selected=dict(env,JAVA_HOME=str(home),PATH=str(home/'bin')+os.pathsep+env.get('PATH',''))
    # Fail closed on missing host libraries or unusable restored runtime, before
    # apksigner can pick an unspecified machine-image Java installation.
    subprocess.run([str(java),'-version'],env=selected,check=True,timeout=30,
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return selected
