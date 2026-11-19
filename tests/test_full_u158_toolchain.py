import gzip,hashlib,importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/upgrades'))
spec=importlib.util.spec_from_file_location('upgrade_toolchain',ROOT/'.circleci/upgrades/toolchain.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrades158/toolchain.json.gz').read_bytes()))
class TargetToolchain(unittest.TestCase):
    def test_exact_target_preimages_and_idempotence(self):
        for kind in ('core_wrapper','core_siso','compiler'):
            with self.subTest(kind=kind):
                text=DATA[kind]['text'];self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),m.HASHES[kind])
                patched=m.transform(kind,text);self.assertNotEqual(text,patched);self.assertEqual(m.transform(kind,patched),patched)
                with self.assertRaises(ValueError):m.transform(kind,text+'# unreviewed drift\n')
        self.assertEqual(hashlib.sha256(DATA['backend']['text'].encode()).hexdigest(),m.HASHES['backend'])
    def test_wrapper_new158_format_is_executable_on_regeneration(self):
        value=m.transform('core_wrapper',DATA['core_wrapper']['text'])
        import ast
        ast.parse(value)
        self.assertIn('os.chmod(wrapper_path, 0o755)',value)
        self.assertNotIn(m.WRAPPER_OLD,value)
    def test_remote_workdir_keeps_canonicalization_and_real_anchor(self):
        value=m.transform('core_siso',DATA['core_siso']['text'])
        self.assertIn('rule["canonicalize_dir"] = True',value)
        self.assertIn('inputs.append("./args.gn")',value)
    def test_native_sisorc_flags_preserved_and_replay(self):
        value='ninja -reapi_keep_exec_stream -fs_min_flush_timeout 300s -reapi_byte_stream_read_threshold 1024 -config googlechrome -local_cache_enable\n'
        result=m.sisorc(value)
        self.assertIn('googlechrome,remote-link',result);self.assertIn('-local_cache_enable',result)
        self.assertIn('-re_cache_enable_write=true',result);self.assertEqual(m.sisorc(result),result)
        for broken in (value.replace('googlechrome','unknown'),value+'ninja -config googlechrome\n',value.replace('300s','1s'),value.strip()+' -re_exec_enable=false\n'):
            with self.assertRaises(ValueError):m.sisorc(broken)
    def test_native_gn_command_always_regenerates_official_graph_without_compiling(self):
        command=m.gn_command();self.assertIn('--force_gn_gen',command);self.assertIn('--ninja=n',command)
        self.assertIn('is_official_build:true',command);self.assertIn('use_siso:true',command);self.assertIn('use_reclient:false',command)
        self.assertNotIn('init',command);self.assertNotIn('sync',command)
        source=(ROOT/'.circleci/upgrades/toolchain.py').read_text()
        self.assertNotIn('prepare-brave-source.sh',source);self.assertNotIn('npm install',source)
    def test_target_backend_uses_pinned_image(self):
        self.assertIn('docker://gcr.io/chops-public-images-prod/rbe/siso-chromium/linux@sha256:d7cb1ab14a0f20aa669c23f22c15a9dead761dcac19f43985bf9dd5f41fbef3a',DATA['backend']['text'])
if __name__=='__main__':unittest.main()
