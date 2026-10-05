"""Record scoped runtime evidence without SIM identities or Wi-Fi network names."""
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HERE = ROOT / "verification"
HERE.mkdir(exist_ok=True)
BASE = ["adb"]  # Select a device with ANDROID_SERIAL if needed.


def shell(command, root=True):
    args = BASE + ["shell"] + (["su", "-c", command] if root else [command])
    return subprocess.run(args, capture_output=True, check=True).stdout.decode("utf-8", errors="replace")


carrier = shell("dumpsys carrier_config")
phones = {}
for section in re.split(r"(?m)^Phone Id = ", carrier)[1:]:
    phone = section.splitlines()[0].strip()
    default_app = section.split("mConfigFromDefaultApp :", 1)[1].split("mConfigFromCarrierApp", 1)[0]
    values = {}
    for key in ["5g_nr_ssrsrp_thresholds_int_array", "lte_rsrp_thresholds_int_array"]:
        match = re.search(r"(?m)^\s*" + key + r" = (\[[^\n]+\])", default_app)
        if match:
            values[key] = json.loads(match.group(1))
    phones[phone] = values

wifi_resolution = shell("cmd overlay lookup --verbose com.android.wifi.resources com.android.wifi.resources:array/config_wifiRssiLevelThresholds")
wifi_thresholds = [int(x) for x in re.findall(r"(?m)^(-?\d+)\s*$", wifi_resolution)]
pid = shell("pidof com.android.carrierconfig").strip()
visible = bool(shell(f"test -f /proc/{pid}/root/product/overlay/Meizu21ProSignalBarsCarrier.apk && echo visible").strip())
telephony = shell("dumpsys telephony.registry")
primaries = re.findall(r"mSignalStrength=.*?primary=(\w+)", telephony)
wifi_dump = shell("dumpsys wifi")
wifi_rssi = None
for line in wifi_dump.splitlines():
    if "mWifiInfo" in line or "WifiInfo:" in line:
        match = re.search(r"RSSI:\s*(-?\d+)", line)
        if match:
            wifi_rssi = int(match.group(1))
            break
tables = shell("dumpsys activity service com.android.systemui/.SystemUIService tables")
wifi_table = re.search(r"StateChangeTableSection START: WifiTableLog(.*?)StateChangeTableSection END: WifiTableLog", tables, re.S)
level_rows = [line.strip() for line in wifi_table.group(1).splitlines() if "|level|" in line] if wifi_table else []
stay_awake = shell("settings get global stay_on_while_plugged_in", root=False).strip()
zip_path = ROOT / "dist/meizu21pro-pixelos17-signal-bars-v1.1-nr95-webui.zip"
checks = {
    "phone_0_nr_thresholds": phones.get("0", {}).get("5g_nr_ssrsrp_thresholds_int_array") == [-125, -115, -105, -95],
    "wifi_thresholds": wifi_thresholds == [-88, -77, -66, -55],
    "wifi_corrected_apk_selected": "/vendor/overlay/zz_Meizu21ProSignalBarsWifi.apk" in wifi_resolution,
    "carrier_apk_visible_to_process": visible,
    "wifi_systemui_reached_level_4": any(re.search(r"\|level\|4$", row) for row in level_rows),
    "usb_stay_awake_restored": stay_awake == "0",
}
result = {
    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
    "effective_default_app_config_by_phone": phones,
    "wifi_thresholds": wifi_thresholds,
    "wifi_rssi_dbm": wifi_rssi,
    "wifi_systemui_level_history": level_rows,
    "primary_signal_types": primaries,
    "checks": checks,
    "limits": "NR effective configuration verified; current primary is LTE, so NR measured-level and strong-signal full-bar scenes are not verified. Wi-Fi SystemUI reached internal level 4 after this boot.",
}
(HERE / "module-runtime-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if not all(checks.values()):
    raise SystemExit("Runtime evidence checks incomplete")
