[app]
title = 港湾汉堡
package.name = gwhbburger
package.domain = cn.gangwan

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = font.ttf

version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0
# 允许 http 明文访问局域网（Android 9+ 默认禁止，这里放开）
android.api = 33
android.minapi = 24
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE
android.allow_backup = True

# 应用名与图标（有 icon.png 才会用，没有就用默认）
# icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
