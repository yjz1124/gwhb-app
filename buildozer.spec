[app]
title = 港湾汉堡
package.name = gwhbburger
package.domain = cn.gangwan

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt,xml

version = 1.0

# requests 依赖的 charset-normalizer 在较新版本会解析出平台轮子（cp314-android），
# 在 p4a 内建环境里装不上 → 固定 2.1.1（只有纯 Python 轮子 py3-none-any，任何平台都能装）
requirements = python3,kivy,charset-normalizer==2.1.1

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 24
android.accept_sdk_license = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE
android.allow_backup = True
android.archs = arm64-v8a, armeabi-v7a

# 允许明文 HTTP：手机要访问店内电脑的 http://IP:8779（安卓 9+ 默认禁止）
android.extra_manifest_application_arguments = ./cleartext.xml

[buildozer]
log_level = 2
warn_on_root = 1
