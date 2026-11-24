"""RawS four-row Home geometry and exact active-source integration (no device)."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECIPE=ROOT/'raws-adblock/production-restore-recipe.json'

def read(name):
    files=json.loads(RECIPE.read_text())['files']
    keys=[p for p in files if p.endswith('/'+name)]
    assert len(keys)==1,(name,keys)
    identity=files[keys[0]]['after_sha256']
    data=(ROOT/'raws-adblock/production-postimages'/identity).read_bytes()
    assert hashlib.sha256(data).hexdigest()==identity
    return data.decode()

def method(s,name):
    start=s.index(name)
    inside=s.index('{',start)
    depth=1
    i=inside+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}')
        i+=1
    return s[start:i]

class RawSHomeGridTest(unittest.TestCase):
    def test_geometry_real_java(self):
        m=read('MostVisitedTilesLayout.java')
        t=read('NewTabPageLayout.java')
        funcs='\n'.join(method(m, 'static int '+name+'(') for name in
                        ['rawSColumns','rawSPageCount','rawSGridRow','rawSGridColumn'])
        funcs+='\n'+method(t,'static int rawSLowerShortcutsGap(')
        src='''class Grid {''' + funcs + '''
          static void check(boolean value) { if (!value) throw new AssertionError(); }
          public static void main(String[] args) {
            check(rawSColumns(360,52)==5);
            check(rawSColumns(200,52)==3);
            check(rawSPageCount(0,5)==1);
            check(rawSPageCount(20,5)==1);
            check(rawSPageCount(21,5)==2);
            check(rawSPageCount(200,5)==10);
            check(rawSGridRow(0,6,5)==0 && rawSGridColumn(0,6,5)==0);
            check(rawSGridRow(1,6,5)==1 && rawSGridColumn(1,6,5)==0);
            check(rawSGridRow(5,6,5)==1 && rawSGridColumn(5,6,5)==4);
            for (int c=1;c<=5;c++) {
              for (int n=1;n<=c*4;n++) {
                int prev=-1;
                for (int i=0;i<n;i++) {
                  int row=rawSGridRow(i,n,c), col=rawSGridColumn(i,n,c);
                  check(row>=0 && row<4 && col>=0 && col<c);
                  check(row*c+col>prev);
                  prev=row*c+col;
                }
                check(rawSGridColumn(n-1,n,c)==(n<c?n-1:c-1));
              }
            }
            int bottom=-1;
            for (int rows=1; rows<=4; rows++) {
              int natural=112+rows*76+48;
              int anchored = rawSLowerShortcutsGap(800,natural,natural,1f)+natural;
              if (bottom>=0) check(anchored==bottom);
              bottom=anchored;
              check(bottom<=800-96);
            }
            check(rawSLowerShortcutsGap(490,128,150,1f)==0);
            check(rawSLowerShortcutsGap(590,600,620,1f)==0);
          }
        }'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Grid.java';p.write_text(src)
            subprocess.run([shutil.which('java'),str(p)],check=True)

    def test_existing_navigation_and_manual_data_owners(self):
        ntp=read('NewTabPage.java')
        grid=read('MostVisitedTilesLayout.java')
        self.assertIn('getControlsPosition()',method(ntp,'private void updateRawSHomeFakeboxVisibility('))
        self.assertIn('fakebox.setVisibility(View.INVISIBLE)',ntp)
        self.assertIn('return false;',method(read('NewTabPageCoordinator.java'),
                                             'boolean usesRawSHomeSearchLauncher('))
        self.assertIn('tiles.restoreRawSGridPage(Integer.parseInt(page))',ntp)
        self.assertIn('RAWS_SHORTCUT_GRID_PAGE',method(ntp,'private void saveRawSShortcutPosition('))
        self.assertIn('getScrollView()',ntp)  # The unchanged actual parent, fallback only.
        self.assertIn('row.setFillViewport(true)',grid)
        self.assertIn('shown ? VISIBLE : INVISIBLE',grid)
        self.assertIn('child.layout(0, 0, 0, 0)',grid)
        self.assertIn('View.LAYOUT_DIRECTION_RTL',grid)
        self.assertIn('if (!mRawSGrid) return;',grid)
        self.assertIn('finishRawSGridRefresh()',read('TileRenderer.java'))
        self.assertIn('max_links = 20;',read('chrome_custom_links_manager_factory.cc'))
        cap=method(read('custom_links_manager_impl.cc'),'bool CustomLinksManagerImpl::AddLinkTo')
        self.assertIn('current_links_.size() >= max_links_',cap)
        self.assertNotIn('.resize(',cap)
        cache=method(read('most_visited_sites.cc'),'void MostVisitedSites::ReloadCustomLinksCache()')
        self.assertIn('manual_custom_links_only',cache)
        self.assertNotIn('StoreLinks',cache)

    def test_real_gate(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from restore_only_feature import load
        manifest=json.loads(RECIPE.read_text())
        a=load(ROOT,manifest['baseline_fingerprint'],manifest['chromium_revision'])
        self.assertEqual(a.identity,hashlib.sha256(RECIPE.read_bytes()).hexdigest())
        self.assertEqual(a.files['chrome/browser/ntp_tiles/chrome_custom_links_manager_factory.cc'][2],'644')


if __name__=='__main__':unittest.main()
