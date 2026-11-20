"""Source contracts; not a GN, CXX Mojo or Android runtime check."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import browser_link as link  # noqa: E402


class BrowserLink(unittest.TestCase):
    def test_client_exact_scope_and_replay(self):
        original = link.CONFIG + "void Hook() {\n" + link.FACTORY_SITE + "}\n"
        updated = link.link_client(original)
        self.assertEqual(updated, link.link_client(updated))
        self.assertEqual(updated.count("MaybeAppendDocumentSubresourceFactory"), 1)
        self.assertEqual(updated.replace(link.FACTORY_LINK, link.FACTORY_SITE)
                         .replace(link.FACTORY_INCLUDE, ""), original)
        for altered in (original.replace("frame, factory_builder", "x"),
                        original + link.FACTORY_SITE):
            with self.assertRaises(ValueError):
                link.link_client(altered)

    def test_browser_android_dep_only_and_replay(self):
        core = (link.CORE + "  sources = [\n" + link.CORE_CLIENT +
                "\n  ]\n  deps = [ \"//base\" ]\n}\n")
        final = link.link_build(core)
        self.assertEqual(final, link.link_build(final))
        self.assertEqual(final.replace(link.CORE_DEP, ""), core)
        self.assertIn(":resources", link.CORE_DEP)
        with self.assertRaises(ValueError):
            link.link_build(core.replace(link.CORE_CLIENT, ""))

    def test_inactive_bounded_and_proxy_transparent(self):
        source = (ROOT / "native/document_subresource_factory.cc").read_text()
        for guard in ("!state.attempted || state.failed", "kMaxPendingChecks = 32",
                      "base::Milliseconds(50)", "request.trusted_params",
                      "request.request_body", "*request.request_initiator != document_origin_",
                      "ERR_BLOCKED_BY_CLIENT", "if (it == pending_.end()) return;",
                      "if (action == Action::kBlock)", "base::IsStringUTF8(text)",
                      "kMaxRulesBytes = 8 * 1024 * 1024"):
            self.assertIn(guard, source)
        self.assertNotIn("FollowRedirect(", source)
        self.assertNotIn("bypass_redirect_checks", source)
        self.assertNotIn("request.url =", source)
        self.assertNotIn("bool ready = true", source)
        self.assertNotIn("raws-fixture", source)
        self.assertNotIn("CommandLine", source)
