# Meizu 21 Pro / PixelOS 17 信号格修正

本版采用用户选定的 NR SS-RSRP 四档 `[-125,-115,-105,-95]`，并将 Wi-Fi RSSI 门槛恢复为 `[-88,-77,-66,-55]`。蜂窝 NR 从 `>= -95 dBm` 起为第四档；Wi-Fi 内部等级恢复为 0..4，使本 ROM 的三格图标能够触达满格。

只适用于本次审计的 PixelOS 17 / Android SDK 37 / meizu21Pro。安装和每次启动均检查原有 CarrierConfig、Wi-Fi 机型覆盖 APK 的 SHA-256；ROM 更新后若哈希改变，两个新覆盖自动停用，避免覆盖新版本的运营商设置。

## 安装

在 KernelSU 管理器安装 `dist/meizu21pro-pixelos17-signal-bars-v1.0-nr95.zip`，然后重启。需要启用提供文件挂载的 metamodule；当前手机使用 hybrid_mount。KernelSU 中还需为 CarrierConfig（com.android.carrierconfig）关闭“卸载模块”挂载隐藏，保持其 root 权限关闭；否则该进程无法读取系统覆盖 APK。本模块不会自动重启或切换网络。

模块包含两个新的静态资源覆盖，分别挂载到 `/product/overlay/Meizu21ProSignalBarsCarrier.apk` 与 `/vendor/overlay/zz_Meizu21ProSignalBarsWifi.apk`。没有替换、重新签名原来的系统 APK。

运营商覆盖完整保留原有 249 段 carrier_config，最后添加一段无过滤条件的 NR 阈值。LTE、IMS、VoNR 和 SA/NSA 配置保持原值。Wi-Fi 覆盖只有一个 RSSI 分档数组，不调整漫游和选网评分。

## 核对生效

重启后在 KernelSU 中点击本模块“操作”，查看新覆盖是否启用及 Wi-Fi 生效数组，并清理可重建的默认运营商配置缓存。CarrierConfig 查询含全局默认和每张卡的配置，不能把全局默认的旧数组误判为当前卡仍用旧值。

ADB 可进一步检查：

```sh
adb shell cmd overlay list com.android.carrierconfig
adb shell cmd overlay list com.android.wifi.resources
adb shell cmd overlay lookup com.android.wifi.resources com.android.wifi.resources:array/config_wifiRssiLevelThresholds
adb shell dumpsys carrier_config
adb shell dumpsys telephony.registry
```

只有当前主信号采用 NR SS-RSRP 时才按新 NR 门槛分档。NSA 下可能仍显示 LTE 锚点的等级；5G 标签不代表一定采用 NR 信号格。

## 单独关闭与回退

卸载整个模块后重启，即恢复 ROM 原值；卸载脚本会清理默认运营商配置缓存。若要禁用整个模块，先点击模块“操作”清理缓存，再立即禁用并重启；单纯禁用可能留下 Android 已缓存的新 NR 门槛。只关闭其中一项，可在模块目录创建对应的空文件，再重启：

```sh
# root shell
touch /data/adb/modules/meizu21pro_signal_bars/disable_nr
touch /data/adb/modules/meizu21pro_signal_bars/disable_wifi
```

删除相应空文件并重启可重新启用该项。首次安装不要创建这些文件，默认两项均启用。

若存在 `/data/adb/modules/meizu21pro_signal_bars/compatibility-error.txt`，说明启动时基准检查不通过，应为新 ROM 重建模块。不要直接再次运行 post-fs-data.sh：它用于挂载前阶段，运行中的挂载资源不会随文件改名立即恢复。

## 实现与限制

该模块调整资源中的信号等级门槛，保留原始测量值，不提高射频接收能力。CarrierConfig 门槛也可能影响基带测量上报 criteria，因此这不是严格仅作用于 SystemUI 的显示 hook。

Android 17 的 CarrierConfigLoader 会按默认运营商应用的版本号恢复磁盘缓存，资源覆盖变化不会改变该版本号。本模块在挂载前定向清理 `/data/user_de/0/com.android.phone/files/carrierconfig-com.android.carrierconfig-*.xml` 中可重建的默认配置，跳过 `-override-` 持久覆盖文件；不清理 Phone 应用数据、SIM 数据或其他运营商应用缓存。

已执行的构建与设备检查见 `dist/build-manifest.json`、`verification/module-verification.json`。安装后的有效配置和图标变化必须在重启后实测；仅生成 idmap 不等于已运行生效。本次 KernelSU 安装已成功。

本次重启后已确认当前卡默认运营商配置的 NR 数组为 `[-125,-115,-105,-95]`，Wi-Fi 生效资源为 `[-88,-77,-66,-55]`，且 CarrierConfig 进程能读取新增 APK。SystemUI 的 Wi-Fi 日志已出现内部等级 4，证明满格对应的等级可以触达。采样时蜂窝主信号为 LTE，因此 NR 实际测量值与格数、强信号满格场景尚未现场验证。运行记录见 `verification/module-runtime-verification.json`；临时 USB 保持亮屏已还原为关闭。

## 重建

使用 Python 3.10+、Java 21、Google AAPT2 与 apksig。基准 APK 和工具由构建者自行准备，默认放在 `inputs/`（也可通过 `SIGNAL_BARS_INPUTS` 环境变量指定目录）。仓库不包含 ROM 原始 APK、工具二进制或签名私钥。现成安装包见 [dist/](dist/)。

在仓库根目录执行以下命令，从适配的 ROM 提取基准 APK：

```powershell
New-Item -ItemType Directory -Force inputs/tools
adb pull /product/overlay/CarrierConfigOverlayMeizu21Pro.apk inputs/
adb pull /vendor/overlay/WifiOverlayMeizu21Pro.apk inputs/
adb pull /system/framework/framework-res.apk inputs/
```

将 Google AAPT2 `9.4.1-15978811` 的 Windows 可执行文件放在 `inputs/tools/aapt2.exe`，将 Google apksig `9.4.1` 放在 `inputs/tools/apksig.jar`。已有构建产物对应的原始 APK 哈希见 [dist/build-manifest.json](dist/build-manifest.json)。

生成自己的开发签名（PKCS12、RSA 2048、别名 `overlay`），不使用原厂签名：

```powershell
keytool -genkeypair -keystore overlay-dev.p12 -storetype PKCS12 -storepass changeit -keypass changeit -alias overlay -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=Signal Bars Development"
```

`changeit` 是此构建器采用的开发密钥默认密码；生成的私钥已由 `.gitignore` 排除。自行重建会得到不同的 APK 签名和哈希。

```powershell
python -m unittest discover -s tests -v
python build.py
```

编译必须使用 `--keep-raw-values`，保留运营商编号的前导零和字符串转义；构建器会比较原始与最终二进制 XML 的全部节点内容，发现额外变化即中止。

Wi-Fi 原覆盖的静态优先级已经是 999（允许的最高值）。AOSP 在优先级相同时按 APK 路径排序，因此新 Wi-Fi APK 使用 `zz_` 前缀，使其排列在原 `WifiOverlayMeizu21Pro.apk` 之后。

## 设备验证脚本

`python verify_runtime.py` 读取实际配置与 SystemUI 等级日志，并写入 `verification/`；不修改设备设置。`python verify_device.py` 执行完整的 27 项安装与生命周期资格检查，需要已构建的 APK、适配 ROM 和 KernelSU root。后者会在手机 `/data/local/tmp` 创建测试目录，并清理可重建的默认 CarrierConfig 缓存（保留持久覆盖）；不安装模块、不重启。连接多台设备时使用 `ANDROID_SERIAL` 环境变量选择目标。完整编译测试需要先准备上述 `inputs/` 和工具。
