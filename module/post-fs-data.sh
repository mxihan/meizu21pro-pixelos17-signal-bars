#!/system/bin/sh
# Runs before filesystem mounting. Never toggle radios or start a background service.
MODDIR=${0%/*}
. "$MODDIR/carrier-cache.sh"
clear_platform_carrier_cache /data/user_de/0/com.android.phone/files || exit 1
COMPATIBLE=1
if [ "$(getprop ro.product.device)" != meizu21Pro ] ||
   [ "$(getprop ro.build.version.sdk)" != 37 ] ||
   ! sha256sum -c "$MODDIR/baseline.sha256" >/dev/null 2>&1; then
    COMPATIBLE=0
    printf '%s\n' 'ROM baseline changed; both overlays withheld. Rebuild for this ROM.' > "$MODDIR/compatibility-error.txt"
else
    rm -f "$MODDIR/compatibility-error.txt"
fi

for COMPONENT in nr wifi; do
    case "$COMPONENT" in
        nr) APK="$MODDIR/system/product/overlay/Meizu21ProSignalBarsCarrier.apk" ;;
        wifi) APK="$MODDIR/system/vendor/overlay/zz_Meizu21ProSignalBarsWifi.apk" ;;
    esac
    if [ "$COMPATIBLE" = 0 ] || [ -e "$MODDIR/disable_$COMPONENT" ]; then
        if [ -f "$APK" ]; then
            mv "$APK" "$APK.disabled" || exit 1
        fi
    elif [ -f "$APK.disabled" ]; then
        mv "$APK.disabled" "$APK" || exit 1
    fi
done
