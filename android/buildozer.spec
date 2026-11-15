[app]
title = Aliens
package.name = aliens
package.domain = org.snxffbxxts
source.dir = app
source.include_exts = py,png,jpg,wav,ttf,ttc,otf
version = 0.1
requirements = python3,pygame,numpy
orientation = portrait
fullscreen = 1
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png
android.presplash_color = #0a090e
android.archs = arm64-v8a
android.api = 34
android.minapi = 24
android.accept_sdk_license = True
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
