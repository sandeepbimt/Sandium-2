"""Frozen raised shortcut artwork contracts and production-Java harness."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]

class ShortcutArtwork(unittest.TestCase):
    def test_production_java(self):
        if not shutil.which('javac') and not os.environ.get('ECJ_JAR'):
            self.skipTest('JDK javac or ECJ_JAR required for production Java harness')
        subprocess.run([sys.executable, str(ROOT/'.circleci/scripts/test-sandium-shortcut-artwork.py')], check=True)

    def test_wallpaper_asset_hash_and_geometry(self):
        import hashlib, importlib.util
        spec=importlib.util.spec_from_file_location('branding',ROOT/'.circleci/scripts/apply-sandium-branding-refresh.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        wallpaper=ROOT/'.circleci/branding/source/wallpaper.webp'
        self.assertEqual(hashlib.sha256(wallpaper.read_bytes()).hexdigest(),module.ASSETS['wallpaper.webp'])
        from PIL import Image
        with Image.open(wallpaper) as image:
            self.assertEqual(image.size,(819,1920))
        source=(ROOT/'.circleci/scripts/apply-sandium-branding-refresh.py').read_text()
        self.assertIn('R.drawable.sandium_wallpaper, 409, 960',source)
