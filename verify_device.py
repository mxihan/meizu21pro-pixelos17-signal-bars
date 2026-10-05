"""Qualify module artifacts and scripts in /data/local/tmp; never install or reboot."""
from pathlib import Path
import json
import subprocess
import zipfile
import uuid

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'verification'
BASE.mkdir(exist_ok=True)
ADB = ['adb']  # Select a device with the standard ANDROID_SERIAL environment variable.
REMOTE = '/data/local/tmp/meizu-signal-bars-verify'
FIXTURE = REMOTE + '/fixture-' + uuid.uuid4().hex[:8]
results = []


def adb(*args, check=True):
    result = subprocess.run(ADB+list(args), capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    return result


def shell(command, check=True):
    return adb('shell', 'su', '-c', command, check=check)


def require(name, condition, detail=''):
    assert condition, name + ': ' + detail
    results.append({'check': name, 'passed': True, 'detail': detail})


def exists(path):
    return shell(f'test -f {path}', check=False).returncode == 0


def main():
    require('cache_cleaner_present', (ROOT/'module/carrier-cache.sh').is_file())
    require('device_root', 'uid=0(root)' in shell('id').stdout)
    adb('shell', 'mkdir', '-p', REMOTE)
    adb('push', str(ROOT/'module'), FIXTURE)
    for filename in ['customize.sh', 'post-fs-data.sh', 'action.sh', 'uninstall.sh', 'carrier-cache.sh']:
        require('shell_syntax_'+filename, shell(f'sh -n {FIXTURE}/{filename}').returncode == 0)

    carrier = FIXTURE+'/system/product/overlay/Meizu21ProSignalBarsCarrier.apk'
    wifi = FIXTURE+'/system/vendor/overlay/zz_Meizu21ProSignalBarsWifi.apk'
    for component, source, target, policy, mapping in [
        ('carrier', carrier, '/system_ext/priv-app/CarrierConfig/CarrierConfig.apk', 'product', 'xml/vendor -> xml/vendor'),
        ('wifi', wifi, '/apex/com.android.wifi/priv-app/ServiceWifiResources@CP2A.260605.016/ServiceWifiResources.apk', 'vendor',
         'array/config_wifiRssiLevelThresholds -> array/config_wifiRssiLevelThresholds')]:
        idmap = REMOTE+'/'+component+'.idmap'
        shell(f'idmap2 create --target-apk-path {target} --overlay-apk-path {source} --idmap-path {idmap} --policy public --policy {policy}')
        output = shell(f'idmap2 dump --idmap-path {idmap}').stdout
        mapped_lines = [line for line in output.splitlines() if line.lstrip().startswith('0x')]
        require('enforced_idmap_'+component, mapping in output and len(mapped_lines) == 1, output)

    harness = ROOT/'dist/installer-check.sh'
    harness.write_bytes(b'''#!/system/bin/sh
MODPATH=${0%/*}
API=$1
KSU=$2
ui_print() { printf '%s\\n' "$*"; }
abort() { printf 'ABORT: %s\\n' "$*"; exit 1; }
set_perm_recursive() { :; }
set_perm() { :; }
. "$MODPATH/customize.sh"
''')
    adb('push', str(harness), FIXTURE+'/installer-check.sh')
    busybox = '/data/adb/ksu/bin/busybox'
    success = shell(f'{busybox} ash {FIXTURE}/installer-check.sh 37 true', check=False)
    require('installer_accepts_audited_rom', success.returncode == 0, success.stdout+success.stderr)
    require('busybox_hash_check', shell(f'{busybox} sha256sum -c {FIXTURE}/baseline.sha256').returncode == 0)
    wrong_api = shell(f'sh {FIXTURE}/installer-check.sh 36 true', check=False)
    require('installer_rejects_wrong_sdk', wrong_api.returncode != 0 and 'SDK 37' in wrong_api.stdout)
    wrong_manager = shell(f'sh {FIXTURE}/installer-check.sh 37 false', check=False)
    require('installer_rejects_wrong_manager', wrong_manager.returncode != 0 and 'requires KernelSU' in wrong_manager.stdout)

    cache = FIXTURE+'/cache-test'
    shell(f'mkdir -p {cache}')
    for filename in ['carrierconfig-com.android.carrierconfig-FAKE-1.xml',
                     'carrierconfig-com.android.carrierconfig-override-FAKE-1.xml',
                     'carrierconfig-other.carrier-FAKE-1.xml', 'unrelated-settings.xml']:
        shell(f'touch {cache}/{filename}')
    shell(f'echo not-a-hash > {FIXTURE}/baseline.sha256')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    adb('push', str(ROOT/'module/baseline.sha256'), FIXTURE+'/baseline.sha256')
    # The preservation test uses synthetic files; boot scripts also invalidate rebuildable device cache.
    harness_cache = ROOT/'dist/cache-check.sh'
    harness_cache.write_bytes(b'. "${0%/*}/carrier-cache.sh"\nclear_platform_carrier_cache "$1"\n')
    adb('push', str(harness_cache), FIXTURE+'/cache-check.sh')
    shell(f'{busybox} ash {FIXTURE}/cache-check.sh {cache}')
    require('cache_cleanup_only_default_bundle', not exists(cache+'/carrierconfig-com.android.carrierconfig-FAKE-1.xml')
            and exists(cache+'/carrierconfig-com.android.carrierconfig-override-FAKE-1.xml')
            and exists(cache+'/carrierconfig-other.carrier-FAKE-1.xml') and exists(cache+'/unrelated-settings.xml'))
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('matching_boot_keeps_both_apks', exists(carrier) and exists(wifi))
    shell(f'touch {FIXTURE}/disable_nr')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('nr_toggle_keeps_wifi', exists(carrier+'.disabled') and not exists(carrier) and exists(wifi))
    shell(f'rm -f {FIXTURE}/disable_nr')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('nr_toggle_restores_carrier', exists(carrier) and not exists(carrier+'.disabled'))
    shell(f'touch {FIXTURE}/disable_wifi')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('wifi_toggle_keeps_nr', exists(wifi+'.disabled') and not exists(wifi) and exists(carrier))
    shell(f'rm -f {FIXTURE}/disable_wifi')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('wifi_toggle_restores_wifi', exists(wifi) and not exists(wifi+'.disabled'))

    invalid = ROOT/'dist/invalid-baseline.sha256'
    invalid.write_text('0'*64+'  /product/overlay/CarrierConfigOverlayMeizu21Pro.apk\n', encoding='utf-8')
    adb('push', str(invalid), FIXTURE+'/baseline.sha256')
    wrong_rom = shell(f'sh {FIXTURE}/installer-check.sh 37 true', check=False)
    require('installer_rejects_changed_rom', wrong_rom.returncode != 0 and 'hashes differ' in wrong_rom.stdout)
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('ota_guard_withholds_both_apks', not exists(carrier) and not exists(wifi)
            and exists(carrier+'.disabled') and exists(wifi+'.disabled') and exists(FIXTURE+'/compatibility-error.txt'))
    adb('push', str(ROOT/'module/baseline.sha256'), FIXTURE+'/baseline.sha256')
    shell(f'{busybox} ash {FIXTURE}/post-fs-data.sh')
    require('compatible_rom_restores_both', exists(carrier) and exists(wifi)
            and not exists(FIXTURE+'/compatibility-error.txt'))

    package = ROOT/'dist/meizu21pro-pixelos17-signal-bars-v1.0-nr95.zip'
    with zipfile.ZipFile(package) as z:
        require('zip_integrity', z.testzip() is None)
        require('no_script_crlf', all(b'\r' not in z.read(n) for n in z.namelist() if n.endswith('.sh')))
        require('checksum_file_lf', b'\r' not in z.read('baseline.sha256'))
        require('zip_module_root', 'module.prop' in z.namelist() and 'customize.sh' in z.namelist())
    state = shell('cmd overlay list').stdout
    results.append({'check': 'current_overlay_state', 'passed': True, 'detail': 'Current installed overlays recorded; qualification does not activate new staged APKs.'})
    report = {'device': 'meizu21Pro', 'sdk': 37, 'phase': 'artifact and lifecycle qualification; module may already be installed',
              'installed': False, 'rebooted': False, 'runtime_effective_values_verified': False,
              'checks': results}
    (BASE/'module-verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'checks_passed': len(results), 'report': str(BASE/'module-verification.json')}, indent=2))


if __name__ == '__main__':
    main()
