[app]
title = 港湾汉堡
package.name = gwhbburger
package.domain = cn.gangwan

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt,xml

version = 1.0

# 依赖链问题：charset-normalizer 3.4+ 发布了 android 平台轮子，p4a 解析必选中它，
# 但装不进 Linux 构建环境（"not a supported wheel"）。解法在 workflow 里用
# PIP_CONSTRAINT 全局钉 charset-normalizer==3.3.2（无安卓轮子的最后版本）。
# 注意：不要在这里钉 requests/charset-normalizer —— 会和 kivy 依赖链解析冲突。
requirements = python3,kivy

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
