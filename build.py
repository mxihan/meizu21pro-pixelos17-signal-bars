"""Build resource-only RROs for the audited PixelOS 17 Meizu 21 Pro build."""
from pathlib import Path
import argparse
import os
import hashlib
import json
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
BASE = Path(os.environ.get('SIGNAL_BARS_INPUTS', str(ROOT / 'inputs'))).resolve()
NR = (-125, -115, -105, -95)
WIFI = (-88, -77, -66, -55)
KEY = '5g_nr_ssrsrp_thresholds_int_array'


def validate_thresholds(thresholds, lower, upper, label):
    if (len(thresholds) != 4 or any(type(x) is not int or not lower <= x <= upper for x in thresholds)
            or any(a >= b for a, b in zip(thresholds, thresholds[1:]))):
        raise ValueError(f'{label} needs four strictly increasing integer thresholds within [{lower},{upper}]')


def wifi_resources(thresholds) -> bytes:
    validate_thresholds(thresholds, -127, 0, 'Wi-Fi')
    return ('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
            '  <integer-array name="config_wifiRssiLevelThresholds">\n'
            + ''.join(f'    <item>{v}</item>\n' for v in thresholds)
            + '  </integer-array>\n</resources>\n').encode('utf-8')


def patch_vendor(xml: bytes, thresholds: tuple[int, ...]) -> bytes:
    validate_thresholds(thresholds, -140, -44, 'NR')
    root = ET.fromstring(xml)
    if root.tag != 'carrier_config_list' or any(x.tag != 'carrier_config' for x in root):
        raise ValueError('expected a carrier_config_list containing carrier_config entries')
    config = ET.SubElement(root, 'carrier_config')
    array = ET.SubElement(config, 'int-array', {'name': KEY, 'num': '4'})
    for value in thresholds:
        ET.SubElement(array, 'item', {'value': str(value)})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def decode_xml(data: bytes) -> ET.Element:
    """Decode the binary XML subset used by the audited vendor.xml, fail closed otherwise."""
    if len(data) < 8 or struct.unpack_from('<HHI', data) != (3, 8, len(data)):
        raise ValueError('not a complete Android binary XML document')
    strings = []
    stack = []
    root = None

    def length(pos, wide=False):
        if wide:
            n = struct.unpack_from('<H', data, pos)[0]
            if n & 0x8000:
                return ((n & 0x7fff) << 16) | struct.unpack_from('<H', data, pos+2)[0], pos+4
            return n, pos+2
        n = data[pos]
        if n & 0x80:
            return ((n & 0x7f) << 8) | data[pos+1], pos+2
        return n, pos+1

    def value(raw, typ, val):
        if raw != 0xffffffff:
            return strings[raw]
        if typ == 3:
            return strings[val]
        if typ == 0x12:
            return 'true' if val else 'false'
        if typ == 0x10:
            return str(val if val < 0x80000000 else val - 0x100000000)
        if typ == 0x11:
            return hex(val)
        raise ValueError(f'unsupported XML value type {typ:#x}; refusing lossy decode')

    pos = 8
    while pos < len(data):
        typ, header, size = struct.unpack_from('<HHI', data, pos)
        if size < header or header < 8 or pos+size > len(data):
            raise ValueError('invalid XML chunk size')
        if typ == 1:
            count, styles, flags, start, _ = struct.unpack_from('<IIIII', data, pos+8)
            if styles:
                raise ValueError('styled XML strings unsupported')
            for index in range(count):
                at = pos + start + struct.unpack_from('<I', data, pos+header+4*index)[0]
                if flags & 0x100:
                    _, at = length(at)
                    n, at = length(at)
                    strings.append(data[at:at+n].decode('utf-8'))
                else:
                    n, at = length(at, True)
                    strings.append(data[at:at+n*2].decode('utf-16le'))
        elif typ == 0x180:
            pass  # resource map; vendor.xml preserves all attribute raw values
        elif typ == 0x102:
            ns, name, attr_start, attr_size, count = struct.unpack_from('<IIHHH', data, pos+16)
            if ns != 0xffffffff or attr_size != 20:
                raise ValueError('unexpected namespaced vendor element or attribute layout')
            node = ET.Element(strings[name])
            for index in range(count):
                at = pos+16+attr_start+index*attr_size
                ans, aname, raw, vsize, _, vtyp, val = struct.unpack_from('<IIIHBBI', data, at)
                if ans != 0xffffffff or vsize != 8:
                    raise ValueError('unexpected namespaced vendor attribute')
                node.set(strings[aname], value(raw, vtyp, val))
            if stack:
                stack[-1].append(node)
            elif root is None:
                root = node
            else:
                raise ValueError('multiple XML roots')
            stack.append(node)
        elif typ == 0x103:
            ns, name = struct.unpack_from('<II', data, pos+16)
            if not stack or ns != 0xffffffff or stack[-1].tag != strings[name]:
                raise ValueError('mismatched XML closing node')
            stack.pop()
        elif typ == 0x104:
            if not stack:
                raise ValueError('text outside XML root')
            idx = struct.unpack_from('<I', data, pos+16)[0]
            text = strings[idx]
            if len(stack[-1]):
                child = stack[-1][-1]
                child.tail = (child.tail or '') + text
            else:
                stack[-1].text = (stack[-1].text or '') + text
        else:
            raise ValueError(f'unsupported XML chunk {typ:#x}; refusing lossy decode')
        pos += size
    if root is None or stack:
        raise ValueError('incomplete XML tree')
    return root


def canonical(node):
    return (node.tag, sorted(node.attrib.items()), node.text or '', node.tail or '',
            [canonical(x) for x in node])


def require_preserved(before, after):
    if canonical(before) != canonical(after):
        raise ValueError('carrier XML changed; refusing to package altered carrier settings')


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_resource_apk(project: Path, unsigned: Path):
    aapt = BASE / 'tools/aapt2.exe'
    compiled = unsigned.with_suffix('.resources.zip')
    run(aapt, 'compile', '--dir', project/'res', '-o', compiled)
    run(aapt, 'link', '-o', unsigned, '-I', BASE/'framework-res.apk',
        '--manifest', project/'AndroidManifest.xml', '--auto-add-overlay',
        '--no-resource-deduping', '--keep-raw-values', compiled)


def build():
    framework = BASE / 'framework-res.apk'
    wifi_xml = wifi_resources(WIFI)
    original_apk = BASE / 'CarrierConfigOverlayMeizu21Pro.apk'
    wifi_apk = BASE / 'WifiOverlayMeizu21Pro.apk'
    with zipfile.ZipFile(original_apk) as z:
        original = decode_xml(z.read('res/xml/vendor.xml'))
    vendor = patch_vendor(ET.tostring(original), NR)
    patched = ET.fromstring(vendor)
    original_part = ET.fromstring(vendor)
    original_part.remove(original_part[-1])
    require_preserved(original, original_part)
    src = ROOT / 'src'
    module = ROOT / 'module'
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    hashes = {'carrier': digest(original_apk), 'wifi': digest(wifi_apk),
              'framework': digest(framework)}
    for kind, target, target_name, partition, filename in [
        ('carrier', 'com.android.carrierconfig', None, 'product', 'Meizu21ProSignalBarsCarrier.apk'),
        ('wifi', 'com.android.wifi.resources', 'WifiCustomization', 'vendor', 'zz_Meizu21ProSignalBarsWifi.apk')]:
        project = src/kind
        res = project/'res'
        res.mkdir(parents=True, exist_ok=True)
        if kind == 'carrier':
            (res/'xml').mkdir(exist_ok=True)
            (res/'xml/vendor.xml').write_bytes(vendor)
        else:
            (res/'values').mkdir(exist_ok=True)
            (res/'values/arrays.xml').write_bytes(wifi_xml)
        name_attr = f' android:targetName="{target_name}"' if target_name else ''
        (project/'AndroidManifest.xml').write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n'
            f' package="io.github.rin.meizu21pro.signalbars.{kind}" android:versionCode="1" android:versionName="1.0">\n'
            ' <uses-sdk android:minSdkVersion="37" android:targetSdkVersion="37"/>\n'
            ' <application android:hasCode="false"/>\n'
            f' <overlay android:targetPackage="{target}"{name_attr} android:isStatic="true" android:priority="999"/>\n'
            '</manifest>\n', encoding='utf-8')
        unsigned = dist/f'{kind}-unsigned.apk'
        compile_resource_apk(project, unsigned)
        output = module/'system'/partition/'overlay'/filename
        output.parent.mkdir(parents=True, exist_ok=True)
        run('java', '-cp', BASE/'tools/apksig.jar', ROOT/'SignApk.java',
            ROOT/'overlay-dev.p12', unsigned, output)
        if kind == 'carrier':
            with zipfile.ZipFile(output) as z:
                roundtrip = decode_xml(z.read('res/xml/vendor.xml'))
            require_preserved(patched, roundtrip)
    manifest = {'nr_ss_rsrp': list(NR), 'wifi_rssi': list(WIFI),
                'baseline_sha256': hashes, 'original_carrier_config_count': len(original),
                'compiled_carrier_config_count': len(patched),
                'apks': {p.name: digest(p) for p in module.rglob('*.apk')}}
    (module/'baseline.sha256').write_bytes((
        hashes['carrier']+'  /product/overlay/CarrierConfigOverlayMeizu21Pro.apk\n'
        +hashes['wifi']+'  /vendor/overlay/WifiOverlayMeizu21Pro.apk\n').encode('utf-8'))
    (dist/'build-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (module/'build-manifest.json').write_bytes((dist/'build-manifest.json').read_bytes())
    package = dist/'meizu21pro-pixelos17-signal-bars-v1.0-nr95.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(module.rglob('*')):
            if path.is_file():
                name = path.relative_to(module).as_posix()
                info = zipfile.ZipInfo(name)
                info.external_attr = ((0o100755 if name.endswith('.sh') else 0o100644) << 16)
                z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    print(json.dumps(manifest, indent=2))
    print('ZIP:', package, 'SHA256:', digest(package))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--decode-only', action='store_true')
    args = parser.parse_args()
    if args.decode_only:
        with zipfile.ZipFile(BASE/'CarrierConfigOverlayMeizu21Pro.apk') as z:
            root = decode_xml(z.read('res/xml/vendor.xml'))
        (BASE/'vendor-original.xml').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))
        print('Decoded carrier entries:', len(root), 'total nodes:', sum(1 for _ in root.iter()))
    else:
        build()
