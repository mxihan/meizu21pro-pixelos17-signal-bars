import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import tempfile
import zipfile

MODULE = Path(__file__).resolve().parents[1] / 'build.py'
if MODULE.exists():
    spec = importlib.util.spec_from_file_location('signal_builder', MODULE)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
else:
    builder = None


class VendorPatchTests(unittest.TestCase):
    fixture = b'''<carrier_config_list>
      <carrier_config><boolean name="vonr_enabled_bool" value="true"/></carrier_config>
      <carrier_config mcc="001" mnc="01"><string name="test">a&amp;b</string>
      <int-array name="lte_rsrp_thresholds_int_array" num="4"><item value="-120"/>
      <item value="-118"/><item value="-114"/><item value="-105"/></int-array>
      </carrier_config></carrier_config_list>'''

    def setUp(self):
        self.assertIsNotNone(builder, 'carrier-preserving builder has not been implemented')

    def test_preserves_every_carrier_entry_and_appends_global_nr_override(self):
        before = ET.fromstring(self.fixture)
        after = ET.fromstring(builder.patch_vendor(self.fixture, (-125, -115, -105, -95)))
        self.assertEqual([ET.tostring(x) for x in before],
                         [ET.tostring(x) for x in list(after)[:-1]])
        final = after[-1]
        self.assertEqual(final.tag, 'carrier_config')
        self.assertEqual(final.attrib, {})
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0].attrib, {'name': '5g_nr_ssrsrp_thresholds_int_array', 'num': '4'})
        self.assertEqual([int(x.attrib['value']) for x in final[0]], [-125,-115,-105,-95])

    def test_rejects_bad_arrays_before_emitting_a_package(self):
        for values in [(-125,-115), (-125,-115,-115,-95), (-125,-115,-105,-150),
                       (-125,-115,-105,-40), (-125,-115,-105,False)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                builder.patch_vendor(self.fixture, values)

    def test_rejects_wrong_document_instead_of_losing_carrier_config(self):
        with self.assertRaises(ValueError):
            builder.patch_vendor(b'<resources/>', (-125,-115,-105,-95))

    def test_rejects_bad_wifi_arrays_before_emitting_resources(self):
        emit = getattr(builder, 'wifi_resources', None)
        self.assertTrue(callable(emit), 'Wi-Fi resource validation has not been implemented')
        for values in [(-88,-77), (-88,-77,-77,-55), (-88,-77,-66,True),
                       (-128,-77,-66,-55), (-88,-77,-66,1)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                emit(values)

    def test_preservation_guard_rejects_corruption_without_assert_statements(self):
        guard = getattr(builder, 'require_preserved', None)
        self.assertTrue(callable(guard), 'mandatory preservation guard has not been implemented')
        before = ET.fromstring(self.fixture)
        after = ET.fromstring(self.fixture)
        after[1].set('mnc', '1')
        with self.assertRaises(ValueError):
            guard(before, after)

    def test_compiler_preserves_zero_prefixed_carrier_codes_and_escaped_strings(self):
        # Dropping raw XML values changes mnc=01 into 1 and emergency dial strings.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project/'res/xml').mkdir(parents=True)
            source = (b'<carrier_config_list><carrier_config mcc="001" mnc="01">'
                      b'<string-array name="dial_strings" num="2"><item value="00"/>'
                      b'<item value="\\#0"/></string-array></carrier_config></carrier_config_list>')
            (project/'res/xml/vendor.xml').write_bytes(source)
            (project/'AndroidManifest.xml').write_text('''<manifest
             xmlns:android="http://schemas.android.com/apk/res/android" package="test.signal.overlay">
             <uses-sdk android:minSdkVersion="37"/>
             <application android:hasCode="false"/>
             <overlay android:targetPackage="com.android.carrierconfig" android:isStatic="true"/>
             </manifest>''', encoding='utf-8')
            output = project/'test.apk'
            builder.compile_resource_apk(project, output)
            with zipfile.ZipFile(output) as z:
                actual = builder.decode_xml(z.read('res/xml/vendor.xml'))
            self.assertEqual(builder.canonical(actual), builder.canonical(ET.fromstring(source)))


if __name__ == '__main__':
    unittest.main()
