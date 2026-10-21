import importlib.util,json,os,sqlite3,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('candidate',Path(__file__).with_name('build_logical_runtime_candidate.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LogicalCandidateTests(unittest.TestCase):
 def test_tw_alias_language_uses_publisher_field_not_glyphs(self):
  # Deliberately swap glyph expectations to detect language guessing.
  a=m.source_aliases('TW','ASCII BRAND',{'chinese_name':'ASCII BRAND','english_name':'含中文原文'})
  self.assertIn(('ASCII BRAND','zh-Hant','OFFICIAL_CHINESE_PRODUCT_NAME'),a)
  self.assertIn(('含中文原文','en','OFFICIAL_ENGLISH_PRODUCT_NAME'),a)
 def test_same_literal_in_both_fields_retains_both_declared_languages(self):
  a=m.source_aliases('TW','SHARED',{'chinese_name':'SHARED','english_name':'SHARED'})
  self.assertEqual({(x[0],x[1]) for x in a},{('SHARED','en'),('SHARED','zh-Hant')})
  self.assertNotEqual(m.stable('alias','drug','SHARED','en'),m.stable('alias','drug','SHARED','zh-Hant'))
  with self.assertRaises(ValueError):m.source_aliases('TW','unsourced',{'chinese_name':'other'})
 def test_identity_is_native_scoped_not_name_merged(self):
  self.assertNotEqual(m.stable('drug','TW','TFDA_LICENSE','123'),m.stable('drug','CA','DPD','123'))
  self.assertEqual(m.stable('drug','TW','TFDA_LICENSE','123'),m.stable('drug','TW','TFDA_LICENSE','123'))
 def test_measure_uses_utf8_and_preserves_original_text(self):
  c=sqlite3.connect(':memory:');c.execute('CREATE TABLE example(name TEXT,metadata_json TEXT)');original='每錠含 １ mg';j=m.js({'raw':original});m.insert(c,'example',name=original,metadata_json=j)
  r,n=m.measure(c,['example']);self.assertEqual(c.execute('select name from example').fetchone()[0],original);self.assertEqual(r['example']['text_blob_bytes'],len(original.encode())+len(j.encode()));self.assertEqual(n,3)
 def test_no_name_only_cross_market_canonical_entity(self):
  self.assertNotEqual(m.stable('ingredient','tfda-43','123','A'),m.stable('ingredient','fr-compo','123','A'))
 def test_created_at_explicit_and_epoch_are_replayable(self):
  with patch.dict(os.environ,{'SOURCE_DATE_EPOCH':'1792540800'}):
   self.assertEqual(m.resolve_created_at(),'2026-10-21T00:00:00+00:00')
   self.assertEqual(m.resolve_created_at('2026-11-18T01:17:00+00:00'),'2026-11-18T01:17:00+00:00')
  with self.assertRaises(ValueError):m.resolve_created_at('2026-10-21T00:00:00')
 def test_source_id_immutable_input_order(self):
  self.assertEqual(m.source_key('feed-sha256-abcd'),'feed');self.assertNotEqual(m.stable('component','feed','record:row/1'),m.stable('component','feed','record:row/2'))
if __name__=='__main__':unittest.main()
