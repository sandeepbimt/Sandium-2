import sys, unittest, threading, http.client
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'probe'))
from compare import check, OFF, ON, OFF2, ON2
from serve import ThreadingHTTPServer, Site

def report(d):return {'suite':'raws-native-probe/1','outcomes':d.copy()}

class Probe(unittest.TestCase):
    def test_matching_fixture(self): self.assertEqual([],check(report(OFF),report(ON),report(ON)))
    def test_no_false_pass_with_both_off(self): self.assertTrue(check(report(OFF),report(OFF),report(OFF)))
    def test_missing_case(self): self.assertRaises(ValueError,check,report(OFF),report(ON),report({}))
    def test_broken_control(self): self.assertTrue(check(report(ON),report(ON),report(ON)))
    def test_late_generic_miss_is_not_parity(self):
        def v2(d): return {'suite':'raws-native-probe/2','outcomes':d.copy()}
        self.assertEqual([], check(v2(OFF2), v2(ON2), v2(ON2)))
        self.assertIn('lateGeneric', check(v2(OFF2), v2(ON2), v2(dict(ON2, lateGeneric='visible')))[0])
        self.assertIn('proceduralControl', check(v2(OFF2), v2(ON2), v2(dict(ON2, proceduralControl='hidden')))[0])
        self.assertRaises(ValueError, check, report(OFF), v2(ON2), v2(ON2))

    def test_origin_routes(self):
        with ThreadingHTTPServer(('127.0.0.1',0),Site) as srv:
            t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
            try:
                for host,path,status in [('raws-news.test','/',200),('raws-ads.test','/raws-fixture/banner.js?keep=yes',200),('raws-news.test','/rules.txt',200),('raws-news.test','/cosmetic-parity',200),('raws-ads.test','/',404),('other','/',400)]:
                    c=http.client.HTTPConnection(*srv.server_address,timeout=3);c.request('GET',path,headers={'Host':host});r=c.getresponse();self.assertEqual(status,r.status);r.read();c.close()
            finally:srv.shutdown();t.join()
