[app]
title = A股异动监控
package.name = stockmonitor
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 0.1
requirements = python3,kivy,pandas,akshare,requests,lxml,charset-normalizer,idna,openssl,pyopenssl
orientation = portrait

[android]
android.api = 33
android.archs = arm64-v8a
android.permissions = INTERNET

[buildozer]
log_level = 2