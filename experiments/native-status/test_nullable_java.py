"""Compile the exact qualified TYPE_USE declarations and exercise old checkpoints."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import patch
import test_prepare
import prepare
import cleanup

class NullableJavaTests(unittest.TestCase):
    def test_generated_qualified_nullable_declarations_compile(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            sources={
                'Nullable.java':'import java.lang.annotation.*; @Target(ElementType.TYPE_USE) @interface Nullable {}',
                'android/view/View.java':'package android.view; public class View {}',
                'android/graphics/ColorFilter.java':'package android.graphics; public class ColorFilter {}',
            }
            code=Path(patch.__file__).read_text()
            declarations=re.findall(r'private android\.view\.@Nullable View \w+;',code)
            self.assertTrue(declarations)
            self.assertIn('public void setColorFilter(android.graphics.@Nullable ColorFilter filter)',code)
            sources['Probe.java']='class Probe { '+ '\n'.join(dict.fromkeys(declarations)) + '\n public void setColorFilter(android.graphics.@Nullable ColorFilter filter) {} }'
            for name,text in sources.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            result=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',str(root/'classes'),*[str(root/x) for x in sources]],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_failed_build_checkpoint_cleanup_and_reapply(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=test_prepare.PrepareTests().fixture(Path(d))
            planned=prepare.plan(src,core,True,True)
            for path,old,new in planned:
                path.write_text(new.replace('android.view.@Nullable View','@Nullable android.view.View').replace('android.graphics.@Nullable ColorFilter','@Nullable android.graphics.ColorFilter'))
            for path,old,new in cleanup.plan(src,core):path.write_text(new)
            replay=prepare.plan(src,core,True,True)
            self.assertEqual({p:n for p,o,n in replay},{p:n for p,o,n in planned})

    def test_mixed_checkpoint_rejected(self):
        with self.assertRaises(ValueError):
            patch.normalize_nullable_checkpoint('private @Nullable android.view.View mSandiumLegacyProtectionHost; private android.view.@Nullable View mSandiumLegacyProtectionHost;')
