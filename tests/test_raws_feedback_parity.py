"""Ensure the #1483 feedback fixes coexist in the one active overlay."""
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RECIPE = json.loads((ROOT / "raws-adblock/production-restore-recipe.json").read_text())["files"]
POST = ROOT / "raws-adblock/production-postimages"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class CombinedFeedback(unittest.TestCase):
    def read(self, filename):
        matches = [entry["after_sha256"] for path, entry in RECIPE.items()
                   if path.endswith("/" + filename)]
        self.assertEqual(len(matches), 1, filename)
        data = (POST / matches[0]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), matches[0])
        return data

    def test_real_home_omnibox_and_real_page_controls_coexist(self):
        toolbar = self.read("ToolbarPhone.java").decode()
        self.assertIn("isRawSBottomNativeHomeOmnibox()", toolbar)
        self.assertIn("mRawSPageActionsActive", toolbar)
        self.assertIn("getRawSUnifiedPaintBounds(", toolbar)
        self.assertIn("tab.canGoForward()", toolbar)
        self.assertIn("centerRawSHomeWallpaper(width, height, mRawSHomeWallpaperCandidate)",
                      self.read("FeedSurfaceCoordinator.java").decode())
        self.assertEqual(hashlib.sha256(self.read("raws_home_wallpaper.webp")).hexdigest(),
                         "6ab6df2f4dab4ff2f9b6d516797564b629c680ca90522ef31f3f4bd3ab34e083")

    def test_appearance_rows_are_visible_but_not_actions(self):
        prefs = ET.fromstring(self.read("appearance_preferences.xml"))
        rows = {row.get(ANDROID + "key"): row for row in prefs.iter()
                if row.get(ANDROID + "key")}
        wanted = ["raws_parity_transition_blur", "raws_parity_darken_transition"]
        for key in wanted:
            r = rows[key]
            for field in ("enabled", "selectable", "persistent"):
                self.assertEqual(r.get(ANDROID + field), "false")
            self.assertIsNone(r.get(ANDROID + "fragment"))
            self.assertFalse(r.findall("intent"))
        self.assertLess(int(rows[wanted[0]].get(ANDROID + "order")),
                        int(rows[wanted[1]].get(ANDROID + "order")))
        self.assertIn("defaultAddressBarColors", self.read("MainSettings.java").decode())


if __name__ == "__main__":
    unittest.main()
