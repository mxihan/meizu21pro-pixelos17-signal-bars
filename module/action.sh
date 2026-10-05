#!/system/bin/sh
MODDIR=${0%/*}
printf '%s\n' 'Expected NR SS-RSRP: [-125,-115,-105,-95]' 'Expected Wi-Fi RSSI: [-88,-77,-66,-55]'
if [ -f "$MODDIR/compatibility-error.txt" ]; then
    cat "$MODDIR/compatibility-error.txt"
fi
for COMPONENT in nr wifi; do
    if [ -e "$MODDIR/disable_$COMPONENT" ]; then
        printf '%s\n' "$COMPONENT: disabled for next boot"
    fi
done
printf '\n%s\n' 'Overlay state:'
cmd overlay list | grep -E 'io.github.rin.meizu21pro.signalbars\.'
printf '\n%s\n' 'Effective Wi-Fi resource:'
cmd overlay lookup com.android.wifi.resources com.android.wifi.resources:array/config_wifiRssiLevelThresholds
printf '\n%s\n' 'CarrierConfig NR arrays (includes default and per-phone config; examine scope):'
dumpsys carrier_config | grep '5g_nr_ssrsrp_thresholds_int_array'
. "$MODDIR/carrier-cache.sh"
if clear_platform_carrier_cache /data/user_de/0/com.android.phone/files; then
    printf '\n%s\n' 'Default carrier cache cleared; persistent overrides preserved.'
    printf '%s\n' 'To disable the entire module: disable it now, then reboot.'
else
    printf '\n%s\n' 'Carrier cache cleanup failed. Resolve this before disabling the module.'
    exit 1
fi
