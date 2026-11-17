"""Selected normal-batch wallpaper packaging; no profile-preference migration."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('branding', ROOT / '.circleci/scripts/apply-sandium-branding-refresh.py')
branding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branding)

class SelectedWallpaperTests(unittest.TestCase):
    def test_fresh_install_upgrade_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'resources/sandium_wallpaper.webp'
            preferences = root / 'profile/preferences.json'
            preferences.parent.mkdir()
            custom = b'{"show_background":false,"custom_wallpaper":"content://user/chosen"}'
            preferences.write_bytes(custom)
            for previous in (None, b'old bundled wallpaper', b'old bundled wallpaper'):
                if previous is not None:
                    destination.write_bytes(previous)
                branding.install_asset(ROOT / '.circleci/branding/source', 'wallpaper.webp', destination)
                self.assertEqual(hashlib.sha256(destination.read_bytes()).hexdigest(), branding.ASSETS['wallpaper.webp'])
                self.assertEqual(preferences.read_bytes(), custom)
    def test_checkpoint_geometry_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Source.java'
            path.write_text('new BackgroundImage(R.drawable.sandium_wallpaper, 270, 480); customWallpaper(path);')
            for _ in range(2):
                branding.refresh_wallpaper_focal_point(path)
                self.assertEqual(path.read_text(), 'new BackgroundImage(R.drawable.sandium_wallpaper, 409, 960); customWallpaper(path);')
    def test_selected_asset_identity(self):
        self.assertEqual(branding.ASSETS['wallpaper.webp'], '6ab6df2f4dab4ff2f9b6d516797564b629c680ca90522ef31f3f4bd3ab34e083')

if __name__ == '__main__':
    unittest.main()
