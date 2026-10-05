import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('builder', Path(__file__).resolve().parents[1] / 'build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class WebPackageTests(unittest.TestCase):
    def test_webui_and_readonly_collector_ship_without_resigning_overlay_apks(self):
        package = getattr(builder, 'package_module', None)
        self.assertTrue(callable(package), 'package-only function not implemented')
        with tempfile.TemporaryDirectory() as temp:
            module, dist = Path(temp) / 'module', Path(temp) / 'dist'
            (module / 'webroot').mkdir(parents=True)
            (module / 'system/vendor/overlay').mkdir(parents=True)
            dist.mkdir()
            (module / 'module.prop').write_bytes(b'version=1.1-nr95-webui\n')
            (module / 'webroot/index.html').write_bytes(b'<title>Status</title>\n')
            (module / 'status.sh').write_bytes(b'#!/system/bin/sh\nprintf status\n')
            (module / 'system/vendor/overlay/wifi.apk').write_bytes(b'signed APK unchanged')
            output = package(module, dist)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read('webroot/index.html'), b'<title>Status</title>\n')
                self.assertEqual(archive.read('system/vendor/overlay/wifi.apk'), b'signed APK unchanged')
                self.assertEqual((archive.getinfo('status.sh').external_attr >> 16) & 0o777, 0o755)


if __name__ == '__main__':
    unittest.main()
