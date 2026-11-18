"""Exact source assembly assertions, no Chromium build/runtime claim."""
from pathlib import Path
import importlib.util,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class GridAdapterTest(unittest.TestCase):
 def test_pristine_source_composition_and_fail_closed(self):
  path=ROOT/'experiments/native-menu'
  sys.path.insert(0,str(path))
  try:
   spec=importlib.util.spec_from_file_location('grid_adapter',path/'grid_adapter.py')
   module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)
    for name in (module.adapter.HANDLER,module.adapter.BUILD,module.APP,module.DRAG):
     target=src/name;target.parent.mkdir(parents=True,exist_ok=True)
     target.write_text((path/'fixtures'/Path(name).name).read_text())
    result=module.plan(src)
    self.assertEqual(len(result),18)
    handler=result[src/module.adapter.HANDLER]
    self.assertIn('mRawSGrid.prepare(mRawSMenu, mDelegate.getMenuItems(), this',handler)
    self.assertIn('RawSMenuGridBinder::pixelHeight',handler)
    self.assertIn('int rawSGridType = adapter.getViewTypeCount();',handler)
    self.assertIn('mRawSGrid.setGridType(rawSGridType);',handler)
    self.assertNotIn('0x5253',handler)
    self.assertIn('setRawSBackHandler(mRawSGrid::backToQuick)',handler)
    self.assertEqual(handler.count('mRawSGrid.close();'),2)
    self.assertIn('mRawSBackHandler.getAsBoolean()',result[src/module.APP])
    self.assertIn('setupBackPressBehaviorForPopupWindow(\n                contentView, () ->',result[src/module.APP])
    self.assertIn('if (mRawSBackHandler == null || !mRawSBackHandler.getAsBoolean()) dismiss();',result[src/module.APP])
    self.assertNotIn('registerOnBackInvokedCallback',result[src/module.APP])
    self.assertIn('rawSVisibleTileTargets()',result[src/module.DRAG])
    self.assertIn('if (fitHeight == 0) return calculateMenuHeight();',result[src/module.APP])
    self.assertEqual(handler.count('!mRawSGrid.isAdjustingViewport()'),2)
    # Planning writes nothing, and unknown native source stops the complete plan.
    before=(src/module.APP).read_text();self.assertNotIn('mRawSBackHandler',before)
    with self.assertRaises(ValueError):module.verify_applied(src)
    for target,content in result.items():target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
    self.assertEqual(module.plan(src),result)
    self.assertEqual(len(module.verify_applied(src)),18)
    (src/module.APP).write_text(result[src/module.APP]+'// unknown\n')
    with self.assertRaises(ValueError):module.plan(src)
  finally:sys.path.remove(str(path))
