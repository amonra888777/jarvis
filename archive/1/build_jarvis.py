#!/usr/bin/env python3
import os, base64, subprocess, shutil, sys
PROJECT_DIR = os.path.expanduser("~/jarvis_unified")
SRC_DIR = os.path.join(PROJECT_DIR, "src")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
APP_NAME = "Jarvis"
APP_DIR = os.path.join(BUILD_DIR, APP_NAME + ".app")
SHARED = base64.b64decode("aW1wb3J0IEZvdW5kYXRpb24KCnB1YmxpYyBzdHJ1Y3QgSmFydmlzTWVzc2FnZTogQ29kYWJsZSB7CiAgICBwdWJsaWMgbGV0IHR5cGU6IFN0cmluZwogICAgcHVibGljIGxldCB0ZXh0OiBTdHJpbmc/CiAgICBwdWJsaWMgbGV0IHNvdXJjZTogU3RyaW5nCiAgICBwdWJsaWMgaW5pdCh0eXBlOiBTdHJpbmcsIHRleHQ6IFN0cmluZz8gPSBuaWwsIHNvdXJjZTogU3RyaW5nKSB7CiAgICAgICAgc2VsZi50eXBlID0gdHlwZQogICAgICAgIHNlbGYudGV4dCA9IHRleHQKICAgICAgICBzZWxmLnNvdXJjZSA9IHNvdXJjZQogICAgfQp9Cg==").decode("utf-8")
