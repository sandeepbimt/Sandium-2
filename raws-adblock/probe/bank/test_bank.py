import io
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from serve import Server
import compare

RUN='aa'*12
class TestBank(unittest.TestCase):
    def setUp(self):
        self.log=io.StringIO()
        self.server=Server(('127.0.0.1',0),self.log)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self,host,path):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        try:
            c.request('GET',path,headers={'Host':host})
            r=c.getresponse()
            return r.status, r.getheader('Location'), r.read()
        finally:
            c.close()

    def sample(self,lane):
        captures={};logs={}
        for i,label in enumerate(compare.LABELS,1):
            active=label.endswith('-on')
            run=f'{i:024x}'
            captures[label]=json.dumps(dict(suite='raws-neutral-bank/1',lane=lane,run=run,
                 origin='http://raws-news.test:8000' if lane=='passive' else 'https://raws-news.test',
                 outcomes=compare.EXPECT[lane][active])).encode()
            events={**dict.fromkeys(compare.NEXT,302),'allowed-direct':200,'allowed-target':200,'excepted-target':200}
            if not active:
                events['blocked-target']=200
            if lane=='scriptlet':
                events={}
            logs[label]='\n'.join(json.dumps(dict(route=k,status=v,run=run)) for k,v in events.items()).encode()
        return captures,logs

    def test_server_really_redirects_without_guessing_from_img(self):
        path='/bank-image/blocked-hop.png?run='+RUN
        status,loc,body=self.get('raws-ads.test',path)
        self.assertEqual((status,loc,body),(302,'/bank-image/blocked-target.png?run='+RUN,b''))
        self.assertEqual(self.get('raws-ads.test',loc)[0],200)
        self.assertEqual([json.loads(x)['route'] for x in self.log.getvalue().splitlines()],['blocked-hop','blocked-target'])
        self.assertEqual(self.get('example.org',path)[0],400)
        self.assertEqual(self.get('raws-ads.test',path+'&foo=bar')[0],400)
        self.assertEqual(self.get('raws-news.test','/fixture-scriptlet/'+RUN)[0],200)
        self.assertEqual(self.get('raws-news.test','/fixture-scriptlet/'+RUN+'?x=y')[0],404)

    def test_case_rows_cannot_infer_block_without_server_or_matched_control(self):
        captures,logs=self.sample('passive')
        rows=compare.compare('passive',captures,logs)
        self.assertTrue(all(v['state']=='expected' for r in rows.values() for v in r.values()))
        logs['raws-on']=b'\n'.join(x for x in logs['raws-on'].splitlines() if b'"blocked-hop"' not in x)
        rows=compare.compare('passive',captures,logs)
        self.assertEqual(rows['raws-on']['blocked-hop']['state'],'invalid-transport-control')
        self.assertEqual(rows['brave-on']['blocked-hop']['state'],'expected')

    def test_reviewed_scriptlet_cannot_reuse_untrusted_or_passive_lane(self):
        captures,logs=self.sample('scriptlet')
        self.assertEqual(compare.compare('scriptlet',captures,logs)['raws-on']['excepted']['state'],'expected')
        wrong=json.loads(captures['raws-on'])
        wrong['origin']='https://raws-news.test:8443'
        captures['raws-on']=json.dumps(wrong).encode()
        with self.assertRaisesRegex(ValueError,'neutral origin'):
            compare.compare('scriptlet',captures,logs)

    def test_missing_same_30_digests_cannot_get_matched_evidence_label(self):
        captures,logs=self.sample('passive')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'meta.json'
            p.write_text(json.dumps(dict(schema='raws-neutral-evidence/1',inventory={'row':'f'*64},runs={})))
            with self.assertRaisesRegex(ValueError,'same 30'):
                compare.qualification(p,'passive',captures,logs,brave_source='a'*40,raws_source='c'*40)

    def test_matched_evidence_binds_exact_lane_sources_and_reports(self):
        captures,logs=self.sample('passive')
        inventory={str(i):f'{i:064x}' for i in range(1,31)}
        inv=compare.digest(json.dumps(inventory,separators=(',',':'),sort_keys=True).encode())
        content=compare.digest(Path(compare.ROOT,'passive.txt').read_bytes())
        runs={}
        for label in compare.LABELS:
            kind,on=label.split('-')
            enable=on=='on'
            runs[label]=dict(platform='android-arm64',apk=('a' if kind=='brave' else 'b')*64,
                 package='com.brave.browser' if kind=='brave' else 'io.github.sandeepbimt.raws',
                 source=('c' if kind=='brave' else 'd')*40,phase='cold',
                 policy='standard' if enable else 'off',provider='additional-url' if enable else 'none',
                 trust='zero-privilege' if enable else 'none',contents=content if enable else None,
                 inventory=inv,report=compare.digest(captures[label]),parser='e'*64 if enable else None,
                 native='f'*64,transport=compare.digest(logs[label]),activation='none' if enable else 'off')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'meta.json'
            p.write_text(json.dumps(dict(schema='raws-neutral-evidence/1',inventory=inventory,runs=runs)))
            compare.qualification(p,'passive',captures,logs,brave_source='c'*40,raws_source='d'*40)
            with self.assertRaisesRegex(ValueError,'exact test RawS'):
                compare.qualification(p,'passive',captures,logs,brave_source='c'*40,raws_source='e'*40)

if __name__=='__main__':
    unittest.main()
