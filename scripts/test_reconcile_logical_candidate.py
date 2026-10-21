import json,unittest
from reconcile_logical_candidate import component_fields,entity_id
class LogicalOriginalFieldTests(unittest.TestCase):
 def test_tw_literal_name_code_strength_basis(self):
  fields=component_fields('TW',{'成分名稱':' 甲Ａ鹽 ','成分代碼':'0001','含量描述':'每錠','含量':'００.５','含量單位':'毫克','處方標示':'A+B'})
  self.assertEqual(fields[:2],(' 甲Ａ鹽 ','0001'));self.assertEqual(json.loads(fields[2]),{'含量描述':'每錠','含量':'００.５','含量單位':'毫克'});self.assertEqual(fields[3:],('毫克','A+B','UNKNOWN'))
 def test_ca_native_field_mapping_does_not_infer_chemical_identity(self):
  fields=component_fields('CA',{'ingredient_name':'X AS SALT','strength':'5','strength_unit':'mg','dosage_unit':'tablet','dosage_value':'1'})
  self.assertEqual(fields[:4],('X AS SALT',None,'5','mg'));self.assertEqual(json.loads(fields[4]),{'dosage_unit':'tablet','dosage_value':'1'});self.assertEqual(fields[5],'ACTIVE')
 def test_france_positional_originals(self):
  fields=component_fields('FR',['123','forme','001','原名','1,25','10 ml','SA','02'])
  self.assertEqual(fields[:4],('原名','001','1,25',None));self.assertEqual(json.loads(fields[4]),{'reference_dosage':'10 ml','element':'forme','source_role_code':'SA','source_link_number':'02'});self.assertEqual(fields[5],'UNKNOWN')
 def test_source_scoped_code_and_exact_name_never_merge_country_or_code(self):
  self.assertNotEqual(entity_id('ingredient','tw','001','X'),entity_id('ingredient','fr','001','X'))
  self.assertNotEqual(entity_id('ingredient','tw','001','X'),entity_id('ingredient','tw','1','X'))
  self.assertNotEqual(entity_id('ingredient','tw','001','X'),entity_id('ingredient','tw','001','x'))
if __name__=='__main__':unittest.main()
