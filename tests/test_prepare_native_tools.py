import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NativeTools(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bin=self.root/'bin';self.bin.mkdir();self.home=self.root/'jdk';(self.home/'bin').mkdir(parents=True)
        self.log=self.root/'apt.log';self.env=dict(os.environ,PATH=str(self.bin)+':/usr/bin:/bin',BASH_ENV=str(self.root/'bashenv'),TEST_ROOT=str(self.root))
        self.write(self.home/'bin/java','echo \'openjdk version "21.0.7"\' >&2')
        self.write(self.home/'bin/javac','echo "javac 21.0.7"')
        self.write(self.bin/'zstd','echo zstd')
        self.write(self.root/'python', 'test ! -f "$TEST_ROOT/missing-yaml"')
        self.write(self.bin/'sudo','echo "sudo $*" >> "$TEST_ROOT/apt.log"; test "$1" = -n; shift; exec "$@"')
        self.write(self.bin/'apt-get', '''echo "apt $*" >> "$TEST_ROOT/apt.log"
if test -f "$TEST_ROOT/fail-apt"; then exit 19; fi
if [[ " $* " == *" install "* ]]; then
  if test ! -f "$TEST_ROOT/no-install"; then
    printf '#!/bin/bash\\necho zstd\\n' > "$TEST_ROOT/bin/zstd"; chmod +x "$TEST_ROOT/bin/zstd"
    rm -f "$TEST_ROOT/missing-yaml"
  fi
fi''')
        s=(ROOT/'tools/prepare_native_tools.sh').read_text().replace('JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64','JAVA_HOME='+str(self.home)).replace('SYSTEM_PYTHON=/usr/bin/python3','SYSTEM_PYTHON='+str(self.root/'python'))
        self.script=self.root/'helper.sh';self.script.write_text(s)
    def write(self,path,body):path.write_text('#!/bin/bash\n'+body+'\n');path.chmod(0o755)
    def run_script(self):return subprocess.run(['bash',str(self.script)],env=self.env,text=True,capture_output=True,timeout=10)
    def test_ready_tools_never_run_apt(self):
        result=self.run_script();self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(self.log.exists())
        self.assertIn(str(self.home),(self.root/'bashenv').read_text())
    def test_installs_only_missing_yaml_with_root_bounds(self):
        (self.root/'missing-yaml').touch();result=self.run_script();self.assertEqual(result.returncode,0,result.stderr)
        log=self.log.read_text();install=[x for x in log.splitlines() if x.startswith('apt ') and ' install ' in x][0]
        self.assertIn('--no-upgrade --no-install-recommends python3-yaml',install)
        self.assertNotIn('jdk',install);self.assertNotIn('zstd',install)
        self.assertIn('sudo timeout --signal=TERM --kill-after=20s 300s env',log.replace('sudo -n','sudo'))
        self.assertIn('DPkg::Lock::Timeout=30',log);self.assertIn('NEEDRESTART_MODE=l',log)
    def test_unusable_zstd_installs_only_zstd(self):
        self.write(self.bin/'zstd','exit 3');result=self.run_script()
        self.assertEqual(result.returncode,0,result.stderr)
        install=[x for x in self.log.read_text().splitlines() if x.startswith('apt ') and ' install ' in x][0]
        self.assertTrue(install.endswith('--no-upgrade --no-install-recommends zstd'))

    def test_broken_existing_java_fails_without_apt(self):
        self.write(self.home/'bin/java','exit 7');result=self.run_script()
        self.assertNotEqual(result.returncode,0);self.assertFalse(self.log.exists())
    def test_failed_apt_does_not_export_success(self):
        (self.root/'missing-yaml').touch();(self.root/'fail-apt').touch();result=self.run_script()
        self.assertEqual(result.returncode,19);self.assertFalse((self.root/'bashenv').exists())
    def test_successful_apt_without_capability_fails_recheck(self):
        (self.root/'missing-yaml').touch();(self.root/'no-install').touch();result=self.run_script()
        self.assertNotEqual(result.returncode,0);self.assertFalse((self.root/'bashenv').exists())
if __name__=='__main__':unittest.main()
