#!/system/bin/sh
# Read-only, scoped output. No cache cleanup, radio changes or persistent writes.
MODDIR=${0%/*}
[ "$(id -u)" = 0 ] || { printf 'Root access required\n' >&2; exit 1; }
query() { timeout 8 "$@" 2>/dev/null || printf '__QUERY_FAILED__\n'; }
printf '@@meta\n'
sed -n 's/^version=/version=/p' "$MODDIR/module.prop"
printf 'device=%s\nsdk=%s\n' "$(getprop ro.product.device)" "$(getprop ro.build.version.sdk)"
for MARKER in disable disable_nr disable_wifi; do
    case "$MARKER" in disable) KEY=disabled ;; disable_nr) KEY=nr_disabled ;; disable_wifi) KEY=wifi_disabled ;; esac
    if [ -e "$MODDIR/$MARKER" ]; then printf '%s=1\n' "$KEY"; else printf '%s=0\n' "$KEY"; fi
done
if sha256sum -c "$MODDIR/baseline.sha256" >/dev/null 2>&1; then printf 'baseline=ok\n'; else printf 'baseline=mismatch\n'; fi
if [ -f "$MODDIR/compatibility-error.txt" ]; then printf 'compatibility_error=1\n'; fi
CARRIER_PID=$(pidof com.android.carrierconfig | awk '{print $1}')
if [ -z "$CARRIER_PID" ]; then printf 'carrier_visible=unknown\n'
elif [ -f "/proc/$CARRIER_PID/root/product/overlay/Meizu21ProSignalBarsCarrier.apk" ]; then printf 'carrier_visible=true\n'
else printf 'carrier_visible=false\n'; fi
printf '@@overlays\n'
query cmd overlay list | grep -E 'io\.github\.rin\.meizu21pro\.signalbars\.|__QUERY_FAILED__'
printf '@@wifi_thresholds\n'
query cmd overlay lookup com.android.wifi.resources com.android.wifi.resources:array/config_wifiRssiLevelThresholds
printf '@@carrier\n'
query dumpsys carrier_config | grep -E 'Default Values from|Phone Id =|mConfigFrom|mPersistentOverrideConfigs|mOverrideConfigs|mNoSimConfig|^[[:space:]]*(5g_nr_ssrsrp_thresholds_int_array|parameters_use_for_5g_nr_signal_bar_int)[[:space:]]*=|__QUERY_FAILED__'
printf '@@telephony\n'
query dumpsys telephony.registry | grep -E '^[[:space:]]*(Phone Id=|mSignalStrength=)|__QUERY_FAILED__'
printf '@@wifi\n'
query dumpsys wifi | awk '
/__QUERY_FAILED__/ {print; next}
/mWifiInfo|WifiInfo:/ {
 if (match($0, /RSSI: *-?[0-9]+/)) print substr($0, RSTART, RLENGTH)
 if (match($0, /Supplicant state: *[A-Z_]+/)) print substr($0, RSTART, RLENGTH)
}'
printf '@@wifi_ui\n'
query dumpsys activity service com.android.systemui/.SystemUIService tables | awk '
/__QUERY_FAILED__/ {print; next}
/StateChangeTableSection START: WifiTableLog/ {active=1; next}
/StateChangeTableSection END: WifiTableLog/ {active=0}
active && /\|level\|/ {print}
'
exit 0
