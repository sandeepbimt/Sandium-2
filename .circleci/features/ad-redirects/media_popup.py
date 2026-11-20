"""Carry scripted video-document popup provenance through Chromium's window IPC."""
import argparse
from pathlib import Path


CORE = "third_party/blink/renderer/core/"
WEB = "third_party/blink/public/web/web_window_features.h"
MOJO = "third_party/blink/public/mojom/window_features/window_features.mojom"
CONVERTER = "content/public/renderer/window_features_converter.cc"
MEDIA_H = CORE + "html/media/html_media_element.h"
MEDIA_CC = CORE + "html/media/html_media_element.cc"
DOM = CORE + "frame/local_dom_window.cc"
CREATE = CORE + "page/create_window.cc"

LOOKUP = """// static
bool HTMLMediaElement::HasConnectedVideo(Document* document) {
  if (!document) {
    return false;
  }
  const auto& map = DocumentToElementSetMap();
  auto entry = map.find(document);
  if (entry == map.end()) {
    return false;
  }
  for (const auto& element : *entry->value) {
    if (element->isConnected() && element->IsHTMLVideoElement()) {
      return true;
    }
  }
  return false;
}

"""
WINDOW_OPEN = """#if BUILDFLAG(IS_ANDROID)
  window_features.sandium_scripted_media_popup =
      HTMLMediaElement::HasConnectedVideo(entered_window->document());
#endif
"""
SYNTHETIC_ANCHOR = """#if BUILDFLAG(IS_ANDROID)
  if (request.GetClientNavigationReason() ==
          ClientNavigationReason::kAnchorClick &&
      request.GetTriggeringEventInfo() ==
          mojom::blink::TriggeringEventInfo::kFromUntrustedEvent &&
      request.GetOriginWindow()) {
    features.sandium_scripted_media_popup =
        HTMLMediaElement::HasConnectedVideo(
            request.GetOriginWindow()->document());
  }
#endif
"""
INCLUDE_MEDIA = '#include "third_party/blink/renderer/core/html/media/html_media_element.h"\n'


def after(anchor, addition):
    return anchor, anchor + addition


def before(anchor, addition):
    return anchor, addition + anchor


EDITS = {
    WEB: [after("  bool always_on_top = false;\n",
                "  bool sandium_scripted_media_popup = false;\n")],
    MOJO: [after("    bool always_on_top = false;\n",
                 "    bool sandium_scripted_media_popup = false;\n")],
    CONVERTER: [
        after("  result->always_on_top = web_window_features.always_on_top;\n",
              "  result->sandium_scripted_media_popup =\n"
              "      web_window_features.sandium_scripted_media_popup;\n"),
        after("  result.always_on_top = window_features.always_on_top;\n",
              "  result.sandium_scripted_media_popup =\n"
              "      window_features.sandium_scripted_media_popup;\n"),
    ],
    MEDIA_H: [after("  static bool IsHLSURL(const KURL&);\n",
                    "  static bool HasConnectedVideo(Document* document);\n")],
    MEDIA_CC: [before("// static\nvoid HTMLMediaElement::OnMediaControlsEnabledChange(Document* document)",
                      LOOKUP)],
    DOM: [
        before('#include "third_party/blink/renderer/core/html/plugin_document.h"\n', INCLUDE_MEDIA),
        after("  WebWindowFeatures window_features =\n"
              "      GetWindowFeaturesFromString(features, entered_window);\n", WINDOW_OPEN),
    ],
    CREATE: [
        after('#include "base/feature_list.h"\n', '#include "build/build_config.h"\n'),
        before('#include "third_party/blink/renderer/core/inspector/console_message.h"\n',
               INCLUDE_MEDIA),
        after("  WebWindowFeatures features(request.GetWindowFeatures());\n", SYNTHETIC_ANCHOR),
    ],
}


def planned(root):
    changes = {}
    for relative, edits in EDITS.items():
        path = root / relative
        source = path.read_text()
        for anchor, patched in edits:
            if source.count(anchor) != 1 or source.count(patched) > 1:
                raise ValueError(f"{relative}: expected one Chromium window-creation anchor")
        present = [patched in source for anchor, patched in edits]
        if all(present):
            continue
        if any(present) or "sandium_scripted_media_popup" in source or "HasConnectedVideo(" in source:
            raise ValueError(f"{relative}: partial scripted media popup integration")
        for anchor, patched in edits:
            source = source.replace(anchor, patched, 1)
        changes[path] = source
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chromium", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    changes = planned(args.chromium)
    if args.verify_only and changes:
        parser.error("Scripted media popup integration is missing")
    for path, source in changes.items():
        path.write_text(source)


if __name__ == "__main__":
    main()
