#!/usr/bin/env python3
"""Execute the actual transformed migration method against deterministic Java doubles."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('overlay',HERE/'apply-sandium-search-choices.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=(HERE.parent.parent/'tests/fixtures/search-choices/BraveSearchEngineAdapter.java').read_text()
source=m.replace(source,m.OLD_ACTIVE,m.NEW_ACTIVE)
start=source.index('    public static void updateActiveDSE(')
end=source.index('    // when readJavaPrefOnly',start)
method=source[start:end]
fixture='''import java.util.*;
public class MigrationTest {
 static class Profile { boolean privateMode; Profile(boolean p){privateMode=p;} }
 static class TemplateUrl { String keyword; boolean prepopulated=true; TemplateUrl(String k){keyword=k;} boolean getIsPrepopulated(){return prepopulated;} int getPrepopulatedId(){return ":g".equals(keyword)?1:0;} String getKeyword(){return keyword;} String getShortName(){return keyword;} }
 static class TemplateUrlService {
  boolean loaded=true,managed=false; List<TemplateUrl> engines=new ArrayList<>(); String chosen;
  boolean isLoaded(){return loaded;} boolean isDefaultSearchManaged(){return managed;}
  List<TemplateUrl> getTemplateUrls(){return engines;} void setSearchEngine(String k){chosen=k;}
 }
 static TemplateUrl selected; static String normal,privateName;
 static class TemplateUrlServiceFactory { static TemplateUrlService service; static TemplateUrlService getForProfile(Profile p){return service;} }
 static String getDSEShortName(Profile p,boolean b,TemplateUrlService s){return "selected";}
 static TemplateUrl getTemplateUrlByShortName(Profile p,String n,TemplateUrlService s){return selected;}
 static void setDSEPrefs(String n,Profile p){if(p.privateMode)privateName=n;else normal=n;}
 '''+method+'''
 static void check(boolean condition){if(!condition)throw new AssertionError();}
 static void run(boolean priv,String old,boolean managed,boolean google,String expected){
  normal="old-normal";privateName="old-private";selected=old==null?null:new TemplateUrl(old);
  TemplateUrlService s=new TemplateUrlService();s.managed=managed;
  if(google)s.engines.add(new TemplateUrl(":g"));
  TemplateUrlServiceFactory.service=s;
  updateActiveDSE(new Profile(priv),s);
  check(Objects.equals(s.chosen,expected));
  boolean migrated=":g".equals(expected)&&!":g".equals(old);
  check(normal.equals(migrated&&!priv?":g":"old-normal"));
  check(privateName.equals(migrated&&priv?":g":"old-private"));
 }
 public static void main(String[] args){
  run(false,":br",false,true,":g"); run(true,":br",false,true,":g");
  run(false,"search.brave.com",false,true,":g");
  run(false,":g",false,true,":g"); run(true,":d",false,true,":d");
  run(false,":br",true,true,":br"); run(true,":br",false,false,":br");
  run(false,null,false,true,null);
  TemplateUrl custom=new TemplateUrl(":g"); custom.prepopulated=false;
  TemplateUrlService s=new TemplateUrlService(); s.engines.add(custom);
  TemplateUrlServiceFactory.service=s; selected=new TemplateUrl(":br"); normal="old";
  updateActiveDSE(new Profile(false),s);check(":br".equals(s.chosen));check("old".equals(normal));
  selected=new TemplateUrl(":br");selected.prepopulated=false;s.engines.add(new TemplateUrl(":g"));
  updateActiveDSE(new Profile(false),s);check(":br".equals(s.chosen));check("old".equals(normal));
  System.out.println("10 migration cases passed");
 }
}
'''
with tempfile.TemporaryDirectory(prefix='search-migration-') as d:
 p=Path(d)/'MigrationTest.java';p.write_text(fixture)
 subprocess.run(['javac',str(p)],check=True)
 subprocess.run(['java','-cp',d,'MigrationTest'],check=True)
