import importlib.util, math, pathlib, unittest, json
R=pathlib.Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,R/'.circleci/scripts'/f'{n}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('apply-sandium-address-progress');c=load('apply-sandium-capture-coherence')
class AddressProgress(unittest.TestCase):
 def source(self,path):
  n=pathlib.Path(path).name
  folders=['address-progress','capture-coherence','progress']
  for f in folders:
   p=R/'tests/fixtures'/f/n
   if p.exists():return p.read_text()
  raise AssertionError(n)
 def composed(self,path):
  s=self.source(path)
  if path.endswith('/ToolbarPhone.java'):s=c.phone(s)
  if path.endswith('/PhoneCaptureStateToken.java'):s=c.token(s)
  return s
 def test_every_pinned_transform_idempotent(self):
  for path,fn in m.TRANSFORMS.items():
   out=fn(self.composed(path));self.assertEqual(out,fn(out),path)
 def test_native_load_state_and_animations_unchanged(self):
  raw=self.source(m.BAR+'ToolbarProgressBar.java');out=m.bar(raw)
  for start,end in [('    public void start() {','    /**\n     * @return True if'),('    public void finish(boolean fadeOut) {','    /**\n     * Hide the progress bar.'),('    private void setProgressInternal(float progress) {','    private void setProgressBarColors() {')]:
   self.assertEqual(raw[raw.index(start):raw.index(end)],out[out.index(start):out.index(end)])
  self.assertIn('onVisibleProgressUpdated() { notifySandiumCapsuleProgress(); }',out)
  self.assertIn('onCompositedLayersVisibilityChanged() { notifySandiumCapsuleProgress(); }',out)
  self.assertIn('mSandiumProgressDetached = true;',out)
  self.assertIn('mSandiumProgressDetached = false;',out)
 def test_capsule_paint_is_clipped_to_the_straight_top_edge(self):
  out=m.drawable(self.source(m.DRAW))
  self.assertLess(out.index('mBackgroundGradient.draw(canvas);'),out.index('canvas.clipPath(mOuterPath);'))
  self.assertLess(out.index('switch (mHairlineBehavior)'),out.index('drawSandiumProgressEdge(canvas);'))
  self.assertIn('mEffectiveBounds.top + Math.max(1f, mStrokePx)',out)
  self.assertIn('canvas.drawRect(left, mEffectiveBounds.top, right, bottom',out)
  self.assertIn('0xFFF4F0E8',out)
  self.assertIn('mSandiumProgressPaint.setAlpha(mSandiumProgressAlpha);',out)
  self.assertNotIn('0xFF46C878',out)
  self.assertNotIn('requestLayout',out)
  self.assertIn('mSandiumProgressRtl ? end - width : start',out)
 def test_thin_layers_suppressed_only_with_capsule_owner(self):
  b=m.bar(self.source(m.BAR+'ToolbarProgressBar.java'))
  a=m.animating(self.source(m.BAR+'ToolbarProgressBarAnimatingView.java'))
  l=m.layer(self.source(m.BAR+'ToolbarProgressBarLayer.java'))
  self.assertIn('if (!isSandiumCapsuleProgressEnabled()) super.draw(canvas);',b)
  self.assertIn('if (!mSandiumCapsuleProgressEnabled) super.draw(canvas);',a)
  self.assertIn('if (mProgressBarView.isSandiumCapsuleProgressEnabled())',l)
  for n in ['progressBar','progressBarBackground','progressBarStaticBackground']:
   self.assertIn('drawingInfo.'+n+'Color = 0;',l)
   self.assertIn('drawingInfo.'+n+'Rect.setEmpty();',l)
 def test_capture_progress_fade_and_destroy(self):
  p=m.phone(self.composed(m.BAR+'top/ToolbarPhone.java'))
  t=m.token(self.composed(m.BAR+'top/PhoneCaptureStateToken.java'))
  self.assertIn('setSandiumCapsuleProgressListener(null)',p)
  self.assertIn('isInTabSwitcherMode()',p)
  self.assertIn('.withSandiumProgressAlpha(sandiumProgressAlpha())',p)
  self.assertIn('mSandiumProgress = progress;',t)
  self.assertIn('current.mSandiumProgressAlpha != next.mSandiumProgressAlpha',t)
  self.assertIn('if (alpha == 0) mSandiumProgress = 0;',t)
 def test_geometry_stays_inside_top_straight_segment(self):
  for width in (0,200,940):
   for radius in (0,16,100,1000):
    inset=max(0,min(radius,width/2));start=inset;end=width-inset
    for f in (0,.01,.5,.99,1):
     for rtl in (False,True):
      progress=(end-start)*f
      left=end-progress if rtl else start;right=end if rtl else start+progress
      self.assertGreaterEqual(left,start);self.assertLessEqual(right,end)
      self.assertAlmostEqual(right-left,progress)
 @unittest.skipUnless(__import__('shutil').which('java'),'Java unavailable')
 def test_exact_capture_token_compile_reset_fade_and_restart(self):
  import re,subprocess,tempfile,shutil
  s=m.token(self.composed(m.BAR+'top/PhoneCaptureStateToken.java'))
  s=re.sub(r'^package .*;\n|^import .*;\n','',s,flags=re.M);s=re.sub(r'@\w+','',s)
  pre='package org.chromium.chrome.browser.toolbar.top;\nimport java.util.Objects;\nclass ColorStateList {int getDefaultColor(){return 0;}}\nclass ButtonData {}\nclass VisibleUrlText {static boolean isVisuallyEquivalent(VisibleUrlText a,VisibleUrlText b){return true;}}\n'
  test='''
class ProgressHarness {
 static PhoneCaptureStateToken make(float progress,int alpha){
  return new PhoneCaptureStateToken(1,2,3,null,0,new VisibleUrlText(),4,new ColorStateList(),true,false,false,progress,100,1,90,true,255).withSandiumProgressAlpha(alpha);
 }
 static void same(PhoneCaptureStateToken a,PhoneCaptureStateToken b,boolean same){
  if ((PhoneCaptureStateToken.getAnyDifference(a,b)==ToolbarSnapshotDifference.NONE)!=same)throw new AssertionError();
 }
 public static void main(String[] args){
  if(PhoneCaptureStateToken.getAnyDifference(make(.2f,255),make(.5f,255))!=ToolbarSnapshotDifference.PROGRESS)throw new AssertionError();
  if(PhoneCaptureStateToken.getAnyDifference(make(.5f,255),make(.5f,128))!=ToolbarSnapshotDifference.PROGRESS)throw new AssertionError();
  same(make(.2f,255),make(.5f,255),false);
  same(make(.5f,255),make(.5f,255),true);
  same(make(1,255),make(1,128),false);
  same(make(1,128),make(1,0),false);
  same(make(1,0),make(0,0),true);
  same(make(1,0),make(.1f,255),false);
  same(make(.5f,0),make(1,0),true);
 }
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'ProgressHarness.java';p.write_text(pre+s+test)
   annotation=pathlib.Path(d)/'ToolbarSnapshotDifference.java'
   annotation.write_text(self.source('ToolbarSnapshotDifference.java'))
   intdef=pathlib.Path(d)/'IntDef.java';intdef.write_text('package androidx.annotation; public @interface IntDef {long[] value() default {};}')
   nullmarked=pathlib.Path(d)/'NullMarked.java';nullmarked.write_text('package org.chromium.build.annotations; public @interface NullMarked {}')
   cmd=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main']
   r=subprocess.run(cmd+['-d',d,str(p),str(annotation),str(intdef),str(nullmarked)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'org.chromium.chrome.browser.toolbar.top.ProgressHarness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   # The #1317 failure must be caught: never synthesize constants from the code under test.
   self.assertIn('ToolbarSnapshotDifference.PROGRESS', s)
   p.write_text(pre+s.replace('ToolbarSnapshotDifference.PROGRESS','ToolbarSnapshotDifference.UNKNOWN')+test)
   r=subprocess.run(cmd+['-d',d,str(p),str(annotation),str(intdef),str(nullmarked)],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0)
   self.assertIn('UNKNOWN',r.stderr)
 def test_composes_with_actual_phone_owners(self):
  bottom=load('apply-sandium-bottom-toolbar');unified=load('apply-sandium-unified-address');refine=load('apply-sandium-toolbar-refinements');home=load('apply-sandium-homepage-surround')
  raw=self.source(m.BAR+'top/ToolbarPhone.java');out=bottom.phone(raw)
  for fn in [unified.phone,unified.phone_leading_shield,unified.phone_shield_state,unified.responsive,refine.phone,refine.capsule_color]:out=fn(out)
  for name,old,new in home.CHANGES:
   if name=='ToolbarPhone.java':out=c.replace(out,old,new)
  out=c.phone(out);out=m.phone(out)
  self.assertEqual(out,m.phone(out))
  for expected in ['SANDIUM_ADDRESS_SHADE_V1','SANDIUM_ADDRESS_HEIGHT_V1','setSandiumToolbarWallpaperPaintColor','mHomeButton.getImageAlpha()).withSandiumProgressAlpha','setSandiumCapsuleProgressListener(null)']:
   self.assertIn(expected,out)
 def test_pipeline_order_and_reset_fixture_coverage(self):
  s=(R/'.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertLess(s.index('apply-sandium-capture-coherence.py'),s.index('apply-sandium-address-progress.py'))
  self.assertIn('apply-sandium-address-progress.py "$SRC" --verify-only',s)
  for path in m.TRANSFORMS:self.assertTrue(self.source(path))
 def test_restore_inventory(self):
  recipe=json.loads((R/'.circleci/features/removal-recipe.json').read_text())
  for path in m.TRANSFORMS:
   self.assertIn(path,recipe['chromium_restore'])
   self.assertIn(path,recipe['ui_only_chromium_restore'])
if __name__=='__main__':unittest.main()
