import sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import process
class Process(unittest.TestCase):
 def test_success_and_resource_stop(self):
  with tempfile.TemporaryDirectory() as t:
   self.assertEqual(process.run([sys.executable,'-c','pass'],t,2,lambda:True)['outcome'],'success')
   r=process.run([sys.executable,'-c','import time; time.sleep(30)'],t,2,lambda:False,grace=.1)
   self.assertEqual(r['outcome'],'time-slice');self.assertLess(r['duration_seconds'],2)
 def test_measurement_exception_kills_owned_writer(self):
  with tempfile.TemporaryDirectory() as t:
   def fail():raise ValueError('measurement failed')
   with self.assertRaises(ValueError):process.run([sys.executable,'-c','import time; time.sleep(30)'],t,2,fail,grace=.1)
if __name__=='__main__':unittest.main()
