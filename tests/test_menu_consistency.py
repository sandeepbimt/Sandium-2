"""Contracts for fixed menu geometry and common icon/label presentation.
Source contracts supplement, not replace, Android device layout verification.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class MenuConsistency(unittest.TestCase):
 def test_height_independent_of_content_and_screen(self):
  height=S[S.index('int preferredHeight('):S.index('private void finishPanelMotion')]
  for forbidden in ('mBody','mHeading','mDraft','mAllMenu','mPage','mNativeVisible','measure('):
   self.assertNotIn(forbidden,height)
  self.assertIn('Math.min(available',height)
  self.assertIn('rows * tileHeight()',height)
  self.assertIn('viewport.setMinimumHeight(((PAGE_SIZE + columns() - 1) / columns()) * tileHeight())',S)
 def test_shared_metrics_and_neutral_labels(self):
  self.assertIn('LinearLayout all = tile()',S)
  self.assertIn('LinearLayout tile = tile()',S)
  self.assertIn('text(value, 12, mTextColor)',S)
  self.assertIn('text(label, 12, mTextColor)',S)
  self.assertNotIn('▦',S)
  self.assertIn('icon.setImageDrawable(allMenuIcon())',S)
  self.assertIn('Gravity.TOP | Gravity.CENTER_HORIZONTAL',S)
  self.assertIn('label.setMaxLines(2)',S)
  self.assertIn('label.setEllipsize(android.text.TextUtils.TruncateAt.END)',S)
 def test_secondary_replaces_not_extends_label_slot(self):
  self.assertIn('tile.removeView(label)',S)
  self.assertIn('addTileLabel(tile, captionSlot)',S)
  self.assertIn('label.setSingleLine(true)',S)
  self.assertIn('control.setSingleLine(true)',S)
  self.assertIn('Math.max(dp(48) + sample.getLineHeight(), sample.getLineHeight() * 2)',S)
  self.assertIn('handler.onItemClick(liveAction, null)',S)
  self.assertIn('tile.setContentDescription(title(entry))',S)
 def test_null_icon_uses_one_slot(self):
  self.assertIn('if (drawable != null) tile.addView(icon',S)
  self.assertIn('icon.setScaleType(ImageView.ScaleType.FIT_CENTER)',S)
 def test_labels_are_localizable_and_native_titles_remain(self):
  import xml.etree.ElementTree as ET,re
  names={x.get('name') for x in ET.parse(ROOT/'android/java/res/values/sandium_menu_strings.xml').getroot()}
  self.assertLessEqual(set(re.findall(r'R.string.(sandium_menu_[a-z_]+)',S)),names)
  self.assertIn('default: return title(entry)',S)
if __name__=='__main__': unittest.main()
