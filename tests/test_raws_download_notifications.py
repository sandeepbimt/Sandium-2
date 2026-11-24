"""Structural guard for the pinned Android download notification integration."""

import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "raws-adblock/production-restore-recipe.json"
ASSETS = ROOT / "raws-adblock/production-postimages"
FACTORY = ("chrome/android/java/src/org/chromium/chrome/browser/download/"
           "DownloadNotificationFactory.java")


def restored(path):
    files = json.loads(RECIPE.read_bytes())["files"]
    digest = files[path]["after_sha256"]
    data = (ASSETS / digest).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise AssertionError(f"payload digest mismatch: {path}")
    return data.decode()


class DownloadNotificationOverlay(unittest.TestCase):
    def test_existing_compile_action_and_permission(self):
        graph = json.loads((ROOT / "tools/frozen_android_owners.json").read_bytes())
        self.assertIn("//" + FACTORY, graph["//chrome/android:chrome_java__compile_java"][1])
        self.assertIn(FACTORY.removeprefix("chrome/android/"),
                      restored("chrome/android/chrome_java_sources.gni"))
        manifest = restored("chrome/android/java/AndroidManifest.xml")
        self.assertEqual(1, manifest.count('android:name="android.permission.POST_PROMOTED_NOTIFICATIONS"'))

    def test_augments_existing_regular_running_notification_only(self):
        factory = restored(FACTORY)
        factory_entry, helper = factory.split("private static Notification decorateRunningDownload(", 1)
        self.assertIn("downloadStatus != DownloadNotificationService.DownloadStatus.IN_PROGRESS",
                      factory_entry)
        self.assertIn("DownloadNotificationFactory", factory_entry)
        self.assertIn("|| downloadUpdate.getProgress().isIndeterminate();", factory_entry)
        self.assertIn("notification.flags |= Notification.FLAG_ONLY_ALERT_ONCE;", helper)
        incognito, _, regular = helper.partition("if (update.getIsDownloadPending())")
        self.assertIn("if (update.getIsOffTheRecord())", incognito)
        self.assertIn("notification.visibility = Notification.VISIBILITY_SECRET;", incognito)
        self.assertNotIn("notification.publicVersion", incognito)
        lockscreen, _, compat = regular.partition("// The request method")
        self.assertIn("notification.visibility = Notification.VISIBILITY_PRIVATE;", lockscreen)
        self.assertIn("R.string.download_started", lockscreen)
        self.assertIn(".setProgress(100, percent, indeterminate)", lockscreen)
        self.assertNotRegex(lockscreen, r"FileName|OriginalUrl|[aA]ddAction|[cC]ontentIntent")
        self.assertIn("Build.VERSION_CODES_FULL.BAKLAVA_1", compat)
        self.assertIn("getImportance() <= NotificationManager.IMPORTANCE_MIN", compat)
        self.assertIn("manager.canPostPromotedNotifications()", compat)
        self.assertIn("notification.clone()", compat)
        self.assertIn("return candidate.hasPromotableCharacteristics() ? candidate : notification;",
                      compat)
        self.assertIn("RuntimeException | LinkageError", compat)
        self.assertNotIn("requestPermissions", factory)


if __name__ == "__main__":
    unittest.main()
