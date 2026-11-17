"""Compile actual generated qualified fields with Chromium's TYPE_USE contract."""
import json,re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HomepageNullable(unittest.TestCase):
 def declarations(self):
  result=[]
  for name in ['backing','paint']:
   for item in json.loads((ROOT/f'.circleci/features/homepage-surround/{name}.json').read_text()):
    text=item['new'] if isinstance(item,dict) else item[2]
    result+=re.findall(r'private (?:@Nullable [a-z][\w.]+|[a-z][\w.]+\.@Nullable \w+) \w+;',text)
  return sorted(set(result))
 def compile(self,fields):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   sources={'Nullable.java':'import java.lang.annotation.*; @Target(ElementType.TYPE_USE) @Retention(RetentionPolicy.CLASS) @interface Nullable {}','Probe.java':'class Probe {\n'+'\n'.join(fields)+'\n}'}
   for field in fields:
    typ=field.split('private ',1)[1].replace('@Nullable ','').split()[0]
    pkg,cls=typ.rsplit('.',1)
    sources[typ.replace('.','/')+'.java']=f'package {pkg}; public class {cls} {{}}'
   for name,text in sources.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   return subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',str(root/'classes'),*[str(root/name) for name in sources]],capture_output=True,text=True)
 def test_actual_generated_fields_compile(self):
  fields=self.declarations();self.assertEqual(7,len(fields))
  r=self.compile(fields);self.assertEqual(0,r.returncode,r.stderr)
 def test_old_scoped_type_syntax_is_rejected(self):
  fields=[re.sub(r'([a-z][\w.]*)\.@Nullable (\w+)',r'@Nullable \1.\2',x) for x in self.declarations()]
  r=self.compile(fields);self.assertNotEqual(0,r.returncode);self.assertIn('scoping construct',r.stderr)
if __name__=='__main__':unittest.main()
