"""Reproduce selected-Python vs apt-system-Python package separation without apt."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.circleci/scripts/ensure-flow-tools.sh'


class FlowTools(unittest.TestCase):
    def harness(self, test_tools, installed):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bin=root/'bin';bin.mkdir();site=root/'apt-site';site.mkdir()
            if installed:(site/'yaml.py').write_text('# simulated apt-owned yaml\n')
            def script(path,source):path.write_text('#!/bin/bash\n'+source);path.chmod(0o755)
            # PATH Python deliberately excludes apt-site; it cannot import yaml.
            script(bin/'python3',f'exec {sys.executable!r} -S "$@"\n')
            system=root/'system-python'
            script(system,f'export PYTHONPATH={str(site)!r}\nexec {sys.executable!r} -S "$@"\n')
            for name in ('zstd','tar'):script(bin/name,'exit 0\n')
            log=root/'apt.log'
            script(bin/'sudo',f'echo "$*" >> {str(log)!r}\nif [[ "$*" == *install* ]]; then echo "# simulated apt-owned yaml" > {str(site/"yaml.py")!r}; fi\n')
            text=SOURCE.read_text()
            self.assertEqual(text.count('SYSTEM_PYTHON=/usr/bin/python3'),1)
            helper=root/'helper.sh';helper.write_text(text.replace('SYSTEM_PYTHON=/usr/bin/python3',f'SYSTEM_PYTHON={str(system)!r}'))
            env=dict(os.environ,PATH=str(bin),PYTHONPATH='')
            selected=subprocess.run([str(bin/'python3'),'-c','import yaml'],env=env,capture_output=True)
            self.assertNotEqual(selected.returncode,0) # reproduce failure despite system package
            result=subprocess.run(['/bin/bash',str(helper)]+(['--with-test-tools'] if test_tools else []),env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return result.stdout,log.read_text() if log.exists() else ''

    def test_system_yaml_not_visible_to_selected_python(self):
        output,apt=self.harness(True,True)
        self.assertIn('FLOW_TEST_YAML=',output);self.assertEqual(apt,'')

    def test_install_targets_system_python_then_rechecks_same_interpreter(self):
        output,apt=self.harness(True,False)
        self.assertIn('apt-get install -y python3-yaml',apt)
        self.assertIn('FLOW_TEST_YAML=',output)

    def test_build_stages_do_not_require_yaml_or_change_python(self):
        output,apt=self.harness(False,False)
        self.assertEqual(apt,'');self.assertNotIn('FLOW_TEST_PYTHON=',output)
        self.assertIn('test_tools=false',output)

    def test_config_uses_shared_helper_everywhere_without_yaml_in_build_stages(self):
        import yaml
        config=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
        for name,job in config['jobs'].items():
            commands=[s['run']['command'] for s in job['steps'] if isinstance(s,dict) and 'run' in s]
            setups=[c for c in commands if 'ensure-flow-tools.sh' in c]
            self.assertEqual(setups,['bash .circleci/scripts/ensure-flow-tools.sh'+(' --with-test-tools' if name=='initialize-full-checkpoint' else '')])
            # Full build-stage wiring uses the standard library, not an apt-only
            # yaml module accidentally imported through the selected Python.
            if name.startswith('full-stage-'):
                self.assertFalse(any('import yaml' in c or 'pip install' in c for c in commands))

if __name__=='__main__':unittest.main()
