[app]
title = 港湾汉堡
package.name = gwhbburger
package.domain = cn.gangwan

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt,xml

version = 1.0

# kivy 依赖 requests → requests 新版依赖 charset-normalizer（有平台专用轮子，
# 在 p4a 内建环境解析/安装必炸）。钉在 2.25.1（依赖 chardet，纯 Python 轮子），
# 整条依赖链全部纯 Python，绕开平台轮子问题
requirements = python3,kivy,requests==2.25.1,chardet==4.0.0

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
