import importlib.util,pathlib,unittest,json
p=pathlib.Path(__file__).with_name('export_log.py');s=importlib.util.spec_from_file_location('export',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_no_sensitive_fields_or_unknown_names(self):
  r=m.safe_trace([{'name':'https://secret.example','ts':0,'args':{}},{'name':'SandiumOrdinaryBlurState','ts':2,'args':{'navigation_id':42,'state':3,'url':'https://secret.example','title':'secret','reason':'secret'}}])
  self.assertNotIn('secret',json.dumps(r));self.assertEqual(r['events'][0]['args'],{'navigation_id':42,'state':3});self.assertEqual(r['events'][0]['correlation'],'navigation_id')
 def test_unlinked_and_bounded(self):
  r=m.safe_trace([{'name':'SandiumDarkPolicyCommit','ts':i,'args':{'incoming':1}} for i in range(m.MAX_EVENTS+10)])
  self.assertEqual(len(r['events']),m.MAX_EVENTS);self.assertEqual(r['truncated_events'],10);self.assertEqual(r['events'][0]['correlation'],'unlinked')
 def test_time_matrix_nonfinite(self):
  r=m.safe_trace([{'name':'SandiumBlurOrigin','ts':0,'args':{'x':float('nan'),'transform':'[1,0,0,0,1,0]'}},{'name':'SandiumBlurOrigin','ts':m.MAX_US+1,'args':{}}]);self.assertEqual(r['events'][0]['args'],{'matrix':[1,0,0,0,1,0]});self.assertEqual(r['truncated_events'],1);self.assertIsNone(m.matrix('password123'))
 def test_logcat_allowlist(self):
  r=m.safe_logcat(['SandiumCaptureOrigin: sample=1,timeMs=2,nativeY=112,url=https://secret,token=secret,nativeAttached=false','other secret']);self.assertNotIn('secret',json.dumps(r));self.assertEqual(r['capture_samples'][0]['nativeAttached'],False)
if __name__=='__main__':unittest.main()
