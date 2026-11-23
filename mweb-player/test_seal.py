"""Synthetic recipe round-trip and negative controls, NOT an Android compile."""
import json, unittest
from seal import ADMISSION, RECIPE, IMAGE, FEATURE, PORT, plan, digest
from glue import BROWSER,WIRE,HEADER,RENDERER,transform
from pathlib import Path
class Recipe(unittest.TestCase):
    def setUp(self):
        self.src={BROWSER:b'  RefreshProceduralCosmetic(frame);\n  if (!IsFrameSiteAdsEnabled(frame)) {',
            WIRE:b'  ApplyRawSObservedGenericStyles(mojo_base.mojom.UnguessableToken document,\n                                 url.mojom.Url expected_url, string css);\n};\n',
            HEADER:b'  void SetRawSProceduralCosmetic(const base::UnguessableToken&,\n                                 uint32_t audited_rule) override;',
            RENDERER:(b'void ChromeRenderFrameObserver::ReadyToCommitNavigation(\n'
                      b'    WebDocumentLoader* document_loader) {\n  // Execute cache clear operations\n'
                      b'void ChromeRenderFrameObserver::SetRawSProceduralCosmetic(\n')}
        self.owners={k:digest(v) for k,v in self.src.items()}; self.inputs={IMAGE+digest(v):v for v in self.src.values()}
        fmt=lambda x:(json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
        self.inputs[RECIPE]=fmt({'files':{k:{'after_sha256':v,'before_sha256':None} for k,v in self.owners.items()},'schema':1});self.man=digest(self.inputs[RECIPE]);self.inputs[ADMISSION]=fmt({'manifest_sha256':self.man, 'staged_vendor_delta':{'sentinel':'unchanged'}});self.proof=digest(self.inputs[ADMISSION]);self.inputs[FEATURE]=f"APPROVED_UI_MANIFEST_SHA256 = '{self.man}'\n".encode();self.inputs[PORT]=f"ADMISSION_SHA256 = '{self.proof}'\n".encode()
    def run_plan(self):return plan(self.inputs.__getitem__,self.owners,self.man,self.proof)
    def test_four_postimages_and_four_metadata_updates(self):
        out=self.run_plan();self.assertEqual(len(out),8)
        m=json.loads(out[RECIPE]);a=json.loads(out[ADMISSION]);self.assertEqual(a['manifest_sha256'],digest(out[RECIPE]));self.assertEqual(a['staged_vendor_delta'],{'sentinel':'unchanged'});self.assertIn(digest(out[RECIPE]).encode(),out[FEATURE]);self.assertIn(digest(out[ADMISSION]).encode(),out[PORT]);
        for k in self.src:
            sha=m['files'][k]['after_sha256'];self.assertEqual(digest(out[IMAGE+sha]),sha);self.assertEqual(self.inputs[IMAGE+self.owners[k]],self.src[k]);self.assertIn(b'StopRawSMobilePlayerFiltering',out[IMAGE+sha]);
        renderer=out[IMAGE+m['files'][RENDERER]['after_sha256']];self.assertIn(Path(__file__).with_name('player.js').read_bytes(),renderer);self.assertIn(b"'https://m.youtube.com'",renderer)
    def test_new_tracked_chromium_owner_and_pin(self):
        path = 'third_party/blink/renderer/core/loader/local_fixture.h'
        src = b'original Chromium bytes'
        admission = json.loads(self.inputs[ADMISSION])
        admission['extra_tracked'] = ['existing/path']
        self.inputs[ADMISSION] = json.dumps(admission, indent=2, sort_keys=True).encode() + b'\n'
        self.proof = digest(self.inputs[ADMISSION])
        self.inputs[PORT] = f"ADMISSION_SHA256 = '{self.proof}'\n".encode()
        def edit(name, original):
            return original + b' and verified delta' if name == path else transform(name, original)
        before = digest(src)
        out = plan(self.inputs.__getitem__, self.owners, self.man, self.proof,
                   edit=edit, tracked={path: (before, src)})
        info = json.loads(out[RECIPE])['files'][path]
        self.assertEqual(info['before_sha256'], before)
        self.assertEqual(out[IMAGE+info['after_sha256']], src + b' and verified delta')
        self.assertEqual(json.loads(out[ADMISSION])['extra_tracked'], ['existing/path', path])
        with self.assertRaisesRegex(ValueError, 'wrong pinned Chromium preimage'):
            plan(self.inputs.__getitem__, self.owners, self.man, self.proof,
                 edit=edit, tracked={path: (before, b'incorrect')})

    def test_stale_owner_refused(self):
        self.inputs[IMAGE+self.owners[HEADER]]+=b'X'
        with self.assertRaises(ValueError):self.run_plan()
    def test_wrong_admission_refused(self):
        self.inputs[ADMISSION]+=b'\n'
        with self.assertRaises(ValueError):self.run_plan()
    def test_ambiguous_anchor_refused(self):
        with self.assertRaises(ValueError):transform(HEADER, self.src[HEADER]*2)
    def test_missing_anchor_refused(self):
        with self.assertRaises(ValueError):transform(RENDERER,b'// Unexpected renderer revision')
    def test_wrong_pin_refused(self):
        self.inputs[PORT]=b"ADMISSION_SHA256 = 'other'"
        with self.assertRaises(ValueError):self.run_plan()

if __name__=='__main__': unittest.main(verbosity=2)
