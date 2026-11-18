from pathlib import Path
import hashlib,json,sys,unittest,yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import generate_feature_seed_config as n
class Preservation(unittest.TestCase):
    def test_normal_config_is_structurally_unchanged(self):
        config=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
        native=n.generate()
        for section in ('parameters','jobs','workflows','job-groups'):
            for key in native.get(section,{}):
                self.assertEqual(config[section].pop(key),native[section][key])
        digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,(ROOT/'ci/normal-config-structure.sha256').read_text().strip())
if __name__=='__main__':unittest.main()
