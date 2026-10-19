import struct,unittest
from play_preflight import elf_page_errors,https_origin,readiness

def elf(align,offset=0):
 data=bytearray(120);data[:6]=b'\x7fELF\x02\x01'
 struct.pack_into('<Q',data,32,64);struct.pack_into('<HH',data,54,56,1)
 struct.pack_into('<IIQQQQQQ',data,64,1,5,offset,0,0,0,0,align)
 return data
class PreflightTests(unittest.TestCase):
 def test_real_current_missing_evidence_is_blocked(self):
  errors=readiness();self.assertTrue(any('Under-13' in e for e in errors));self.assertTrue(any('drafts' in e for e in errors))
  self.assertTrue(any('preLaunchReportReviewed' in e for e in errors))
  self.assertFalse(any('preLaunchReportReviewed' in e for e in readiness(stage='build')))
 def test_16kb_segments_and_congruence(self):
  self.assertFalse(elf_page_errors(elf(16384),'good.so'))
  self.assertTrue(elf_page_errors(elf(4096),'bad.so'))
  self.assertTrue(elf_page_errors(elf(16384,4096),'bad-offset.so'))
  self.assertTrue(elf_page_errors(b'\x7fELF','truncated.so'))
 def test_stable_origin_only(self):
  self.assertTrue(https_origin('https://api.plazr.cc'))
  for value in ('http://plazr.cc','https://foo.trycloudflare.com','https://user:password@plazr.cc','https://plazr.cc/path','https://plazr.cc?x=y'):
   self.assertFalse(https_origin(value))
if __name__=='__main__':unittest.main()
