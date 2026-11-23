"""Exact-source ordering and negative controls, not Android-runtime evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

import glue


ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def between(s, begin, end):
    pos = s.index(begin)
    return s[pos:s.index(end, pos + len(begin))]


def runs_before(body, first, second):
    return body.index(first) < body.index(second)


class EarlyGlue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / 'raws-adblock/production-postimages'
        cls.base = {}
        cls.out = {}
        cls.manifest = json.loads((ROOT / 'raws-adblock/production-restore-recipe.json').read_text())
        for name, digest in glue.OWNERS.items():
            path = cls.preimages / name if name in glue.NEW_TRACKED else source / digest
            data = path.read_bytes()
            if sha(data) != digest:
                raise ValueError('wrong #1514 input: ' + name)
            cls.base[name] = data.decode()
            cls.out[name] = glue.transform(name, data).decode()

    def test_exact_product_composition(self):
        self.assertTrue(glue.USES_COMMIT_POLICY)
        self.assertEqual(set(glue.NEW_TRACKED), set(glue.UPSTREAM))
        for name in self.out:
            self.assertNotEqual(self.base[name], self.out[name])
            with self.assertRaises(ValueError):
                glue.transform(name, b'// shifted or missing anchor')

    def test_policy_is_false_for_defaults_error_and_alternate_constructors(self):
        self.assertIn('bool raws_mobile_player_filtering = false;',
                      self.out[glue.NAV_MOJOM])
        self.assertIn('bool raws_mobile_player_filtering = false;',
                      self.out[glue.WEB_PARAMS])
        for name, count in ((glue.NAV, 2), (glue.NAV_CONTROLLER, 1), (glue.NAV_ENTRY, 1)):
            text = self.out[name]
            self.assertEqual(text.count('CommitNavigationParams::New('), count)
            self.assertEqual(text.count('/*raws_mobile_player_filtering=*/false);'), count)
        err = between(self.out[glue.NAV],
                      '  // Error main documents use the default.',
                      '  GetRenderFrameHost()->FailedNavigation(')
        self.assertNotIn('raws_mobile_player_filtering', err)

    def test_authorization_is_by_browser_for_final_primary_commit(self):
        nav = self.out[glue.NAV]
        gate = between(nav, '  // Compute from the final URL', '  auto response_head = response_head_.Clone();')
        for guard in ('IsInPrimaryMainFrame()', '!origin_to_commit.opaque()', '!IsPdf()',
                      '!commit_params_->is_view_source',
                      'GetWebContents(), GetURL(), origin_to_commit'):
            self.assertIn(guard, gate)
        self.assertTrue(runs_before(gate, 'ShouldFilterRawSMobilePlayer(', 'commit_params_.Clone()'))
        policy = between(self.out[glue.CHROME_CC],
                         'bool ChromeContentBrowserClient::ShouldFilterRawSMobilePlayer(',
                         'int ChromeContentBrowserClient::GetRawSPageTextPolicyForNavigation(')
        for guard in ('BUILDFLAG(IS_ANDROID)', 'url.SchemeIs("https")', 'url.host() == "m.youtube.com"',
                      '!url.has_username()', '!url.has_password()', '!url.has_port()',
                      'final_origin.IsSameOriginWith(url::Origin::Create(url))',
                      'web_contents->GetBrowserContext(), final_origin'):
            self.assertIn(guard, policy)
        self.assertIn('return false;', policy)
        self.assertIn('return false;', between(self.out[glue.CONTENT_CC],
                      'bool ContentBrowserClient::ShouldFilterRawSMobilePlayer(',
                      'int ContentBrowserClient::GetRawSPageTextPolicyForNavigation('))

    def test_exact_preparser_event_chain_not_browser_did_finish(self):
        blink = self.out[glue.LOADER_CC]
        commit = between(blink, '  DidInstallNewDocument(document);',
                         'void DocumentLoader::CreateParserPostCommit()')
        self.assertTrue(runs_before(commit, 'DispatchDidCommitLoad(', 'StartLoadingResponse();'))
        load = between(blink, 'void DocumentLoader::StartLoadingResponse()',
                       '  // The main document from an MHTML archive is not loaded')
        self.assertIn('CreateParserPostCommit();', load)
        content = self.out[glue.RENDER_FRAME]
        self.assertIn('commit_params.raws_mobile_player_filtering;', content)
        renderer_notify = between(content, 'void RenderFrameImpl::DidCommitNavigation(',
                                 'observer.DidCreateNewDocument();')
        self.assertIn('observer.ReadyToCommitNavigation(document_loader);', renderer_notify)
        self.assertIn('raws_mobile_player_filtering_(params_->raws_mobile_player_filtering)', blink)
        self.assertIn('const bool raws_mobile_player_filtering_;', self.out[glue.LOADER_H])
        renderer = self.out[glue.RENDERER]
        early = between(renderer, 'void ChromeRenderFrameObserver::ReadyToCommitNavigation(',
                        'void ChromeRenderFrameObserver::DidSetPageLifecycleState(')
        for guard in ('render_frame()->IsMainFrame()', 'document_loader->RawSMobilePlayerFiltering()',
                      'frame->GetDocumentLoader() == document_loader',
                      'RunRawSMobilePlayerFiltering(*frame, /*enabled=*/true)'):
            self.assertIn(guard, early)
        standalone = between(renderer, 'void RunRawSMobilePlayerFiltering(',
                             'void ChromeRenderFrameObserver::ReadyToCommitNavigation(')
        self.assertIn('EvaluationTiming::kSynchronous', standalone)
        self.assertIn('UserActivationOption::kDoNotActivate', standalone)
        self.assertIn('WantResultOption::kNoResult', standalone)
        self.assertIn('frame.IsInFencedFrameTree()', standalone)
        self.assertIn('frame.IsProvisional()', standalone)
        self.assertIn((ROOT / 'mweb-player/player.js').read_text(), standalone)

    def test_late_message_is_disable_only_and_document_bound(self):
        wire = self.out[glue.WIRE]
        self.assertNotIn('SetRawSMobilePlayerFiltering', wire)
        self.assertIn('StopRawSMobilePlayerFiltering(mojo_base.mojom.UnguessableToken document);', wire)
        browser = self.out[glue.BROWSER]
        stop = between(browser, '  RefreshProceduralCosmetic(frame);\n  if (!IsFrameSiteAdsEnabled(frame)) {',
                       '    SetAutomaticElementStyles(frame, {});')
        self.assertIn('frame.IsInPrimaryMainFrame()', stop)
        self.assertIn('remote->StopRawSMobilePlayerFiltering(*document);', stop)
        renderer_stop = between(self.out[glue.RENDERER],
                               'void ChromeRenderFrameObserver::StopRawSMobilePlayerFiltering(',
                               'void ChromeRenderFrameObserver::SetRawSProceduralCosmetic(')
        self.assertIn('frame->GetEmbeddingToken() == token', renderer_stop)
        self.assertIn('RunRawSMobilePlayerFiltering(*frame, /*enabled=*/false)', renderer_stop)
        self.assertNotIn('/*enabled=*/true', renderer_stop)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preimages', type=Path, required=True)
    EarlyGlue.preimages = parser.parse_args().preimages
    unittest.main(argv=[__file__], verbosity=2)
