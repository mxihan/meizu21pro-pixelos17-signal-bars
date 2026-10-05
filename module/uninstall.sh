#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/carrier-cache.sh"
clear_platform_carrier_cache /data/user_de/0/com.android.phone/files
