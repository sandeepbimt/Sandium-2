import unittest
from policy import Candidate, Context, Kind, Match, Verdict


class PolicyTests(unittest.TestCase):
    def candidate(self, kind=Kind.POPUP, native=True, shields=True):
        return Candidate(Context('https://ad.test', 'https://frame.test',
                                 'https://root.test', kind), native, shields)

    def test_native_denial_cannot_be_overridden(self):
        self.assertEqual(self.candidate(native=False).begin('https://login.test'), (Verdict.BLOCK, None))

    def test_shields_off_preserves_native_allow(self):
        self.assertEqual(self.candidate(shields=False).begin('https://ad.test'), (Verdict.ALLOW, None))

    def test_legitimate_controls_without_matching_rule(self):
        for url in ('https://login.test', 'https://payment.test', 'https://link.test'):
            c = self.candidate()
            verdict, token = c.begin(url)
            self.assertEqual(verdict, Verdict.DEFER)
            self.assertEqual(c.complete(token, Match()), Verdict.ALLOW)

    def test_exception_and_important(self):
        for result, expected in ((Match(blocked=True), Verdict.BLOCK),
                                 (Match(blocked=True, excepted=True), Verdict.ALLOW),
                                 (Match(blocked=True, excepted=True, important=True), Verdict.BLOCK)):
            c = self.candidate()
            _, token = c.begin('https://ad.test')
            self.assertEqual(c.complete(token, result), expected)
            self.assertEqual(c.complete(token, result), Verdict.CANCEL)

    def test_redirect_keeps_opener_and_invalidates_stale_reply(self):
        c = self.candidate()
        _, old = c.begin('about:blank')
        _, new = c.begin('https://redirect.test')
        self.assertEqual(new[1].frame_opener, 'https://frame.test')
        self.assertEqual(new[1].root_opener, 'https://root.test')
        self.assertEqual(c.complete(old, Match(blocked=True)), Verdict.CANCEL)
        self.assertEqual(c.complete(new, Match()), Verdict.ALLOW)

    def test_destroyed_or_finished_candidate_cannot_resume(self):
        c = self.candidate()
        _, token = c.begin('https://payment.test')
        c.invalidate()
        self.assertEqual(c.complete(token, Match()), Verdict.CANCEL)
        self.assertEqual(c.begin('https://later.test'), (Verdict.CANCEL, None))

    def test_distinct_request_types(self):
        for kind in Kind:
            _, token = self.candidate(kind).begin('https://ad.test')
            self.assertIs(token[1].kind, kind)
        self.assertNotEqual(Kind.POPUP, Kind.POPUNDER)
        self.assertNotIn('document', [kind.value for kind in Kind])

    def test_requires_resolved_opener(self):
        with self.assertRaises(ValueError):
            Candidate(Context('https://ad.test', '', '', Kind.POPUP), True, True)


if __name__ == '__main__':
    unittest.main()
