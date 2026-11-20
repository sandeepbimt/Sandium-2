"""Host regression checks for the renderer provenance carried to CanCreateWindow."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import media_popup as popup


def write_anchor_fixture(root):
    for name, edits in popup.EDITS.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(anchor for anchor, _ in edits))


class ScriptedMediaPopup(unittest.TestCase):
    def test_transform_and_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_anchor_fixture(root)
            changes = popup.planned(root)
            self.assertEqual(len(changes), len(popup.EDITS))
            for path, source in changes.items():
                path.write_text(source)
            self.assertEqual(popup.planned(root), {})
            converter = root / popup.CONVERTER
            anchor, replaced = popup.EDITS[popup.CONVERTER][1]
            converter.write_text(converter.read_text().replace(replaced, anchor))
            with self.assertRaises(ValueError):
                popup.planned(root)

    def test_script_and_anchor_provenance(self):
        # Only Blink's DOM window.open call site uses WINDOW_OPEN. HTML and SVG
        # supply the anchor reason and event trust. Forms have separate reasons.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "provenance.cc"
            common = """
#include <cassert>
#include <vector>
#define BUILDFLAG(flag) ANDROID
struct Document {};
struct HTMLMediaElement {
  bool connected, video;
  bool isConnected() const { return connected; }
  bool IsHTMLVideoElement() const { return video; }
  static bool HasConnectedVideo(Document*);
};
struct Entry { Document* key; std::vector<HTMLMediaElement*>* value; };
struct Map {
  std::vector<Entry> rows;
  auto find(Document* key) const {
    auto entry = rows.begin();
    while (entry != rows.end() && entry->key != key) ++entry;
    return entry;
  }
  auto end() const { return rows.end(); }
};
Map& DocumentToElementSetMap() { static Map map; return map; }
struct Features { bool sandium_scripted_media_popup = false; };
struct Window { Document* doc; Document* document() const { return doc; } };
enum class ClientNavigationReason { kNone, kAnchorClick, kFormSubmissionPost };
namespace mojom::blink {
enum class TriggeringEventInfo { kUnknown, kFromTrustedEvent, kFromUntrustedEvent };
}
using Trust = mojom::blink::TriggeringEventInfo;
struct Request {
  Window* origin;
  ClientNavigationReason reason;
  Trust trust;
  auto GetClientNavigationReason() const { return reason; }
  auto GetTriggeringEventInfo() const { return trust; }
  auto GetOriginWindow() const { return origin; }
};
"""
            source.write_text(common + popup.LOOKUP + """
Features Open(Window* entered_window) {
  Features window_features;
""" + popup.WINDOW_OPEN + """
  return window_features;
}
Features Create(Features features, Request request) {
""" + popup.SYNTHETIC_ANCHOR + """
  return features;
}
int main() {
  using R = ClientNavigationReason;
  Document player, other;
  Window media{&player}, elsewhere{&other};
  HTMLMediaElement audio{true, false}, detached_video{false, true};
  std::vector<HTMLMediaElement*> media_set{&audio, &detached_video};
  DocumentToElementSetMap().rows.push_back({&player, &media_set});
  assert(!Open(&media).sandium_scripted_media_popup);
  detached_video.connected = true;
  assert(Open(&media).sandium_scripted_media_popup == ANDROID);
  assert(!Open(&elsewhere).sandium_scripted_media_popup);
  auto auxiliary = [&](R reason, Trust trust, Window* origin = nullptr) {
    return Create({}, {origin, reason, trust}).sandium_scripted_media_popup;
  };
  assert(auxiliary(R::kAnchorClick, Trust::kFromUntrustedEvent, &media) == ANDROID);
  assert(!auxiliary(R::kAnchorClick, Trust::kFromTrustedEvent, &media));
  assert(!auxiliary(R::kAnchorClick, Trust::kUnknown, &media));
  assert(!auxiliary(R::kAnchorClick, Trust::kFromUntrustedEvent));
  assert(!auxiliary(R::kAnchorClick, Trust::kFromUntrustedEvent, &elsewhere));
  assert(!auxiliary(R::kFormSubmissionPost, Trust::kFromUntrustedEvent, &media));
  assert(!auxiliary(R::kNone, Trust::kUnknown, &media));
  assert(Create(Open(&media), {&media, R::kNone, Trust::kUnknown})
             .sandium_scripted_media_popup == ANDROID);
}
""")
            for android in (0, 1):
                binary = root / "provenance"
                subprocess.run(["c++", "-std=c++20", f"-DANDROID={android}",
                                str(source), "-o", str(binary)], check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
