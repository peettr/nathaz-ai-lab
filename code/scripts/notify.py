#!/usr/bin/env python3
"""Send Telegram notification. Usage: python3 notify.py "message" """
import sys, urllib.request, urllib.parse

TOKEN = "8784162677:AAF-L_qNulpvcV_I6VcnHCPKOIoM4MVUAVE"
CHAT = "6701874922"

msg = sys.argv[1] if len(sys.argv) > 1 else "Test notification"
data = urllib.parse.urlencode({"chat_id": CHAT, "text": msg}).encode()
urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data)
print("sent")
