import os
import sys
import subprocess
import time
import io
import json
import base64
import threading
import urllib.request

import socket
import functools

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

print = functools.partial(print, flush=True)

from PIL import Image
import paho.mqtt.client as mqtt
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__)

ADB_PATH = r"C:\Users\shahi\AppData\Local\Android\Sdk\platform-tools\adb.exe"
TEMP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_SCREEN_PATH = os.path.join(TEMP_DIR, "web_screen.png")
CURRENT_FORCED_DICE = 0
DEFAULT_ROOM = "LUDO88"
ACTIVE_ROOMS = set([DEFAULT_ROOM])
TARGET_PHONE_IP = "192.168.1.3"

_screen_cache = {"time": 0, "b64": "", "bytes": b""}
_screen_lock = threading.Lock()

def run_adb(cmd_list, timeout=6):
    full_cmd = [ADB_PATH] + cmd_list
    for attempt in range(3):
        try:
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            out = res.stdout.strip()
            err = res.stderr.strip()
            comb = (out + " " + err).lower()
            if "device offline" in comb or "not found" in comb or "daemon not running" in comb:
                time.sleep(0.5)
                subprocess.run([ADB_PATH, "connect", "127.0.0.1:5555"], capture_output=True, timeout=3)
                continue
            return out, err
        except Exception:
            time.sleep(0.4)
    return "", "adb execution timeout"

def get_connected_devices():
    out, _ = run_adb(["devices"])
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    if not devices:
        run_adb(["connect", "127.0.0.1:5555"])
        out, _ = run_adb(["devices"])
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
    return devices

def get_primary_device():
    devs = get_connected_devices()
    return devs[0] if devs else None

def capture_screen_cached(max_age=0.25):
    global _screen_cache
    now = time.time()
    with _screen_lock:
        if now - _screen_cache["time"] < max_age and _screen_cache["b64"]:
            return _screen_cache["b64"], _screen_cache["bytes"]
        
        dev = get_primary_device()
        if not dev:
            return "", b""
        
        try:
            run_adb(["-s", dev, "shell", "screencap", "-p", "/sdcard/remote_sc.png"], timeout=3)
            run_adb(["-s", dev, "pull", "/sdcard/remote_sc.png", TEMP_SCREEN_PATH], timeout=3)
            if os.path.exists(TEMP_SCREEN_PATH):
                im = Image.open(TEMP_SCREEN_PATH).convert("RGB")
                im_small = im.resize((360, 640), Image.Resampling.BILINEAR)
                buf = io.BytesIO()
                im_small.save(buf, format="JPEG", quality=65)
                raw_bytes = buf.getvalue()
                b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                
                _screen_cache = {"time": now, "b64": b64_str, "bytes": raw_bytes}
                return b64_str, raw_bytes
        except Exception as e:
            print(f"[SCREEN ERROR] {e}")
        return "", b""

def send_http_to_phone(ip, path):
    def _run():
        try:
            s = socket.socket()
            s.settimeout(0.6)
            s.connect((ip, 8088))
            s.sendall(f"GET {path} HTTP/1.1\r\nHost: {ip}:8088\r\nConnection: close\r\n\r\n".encode())
            s.recv(512)
            s.close()
            print(f"[PHONE] Success: {path} -> {ip}:8088")
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()

def apply_set_dice(val):
    global CURRENT_FORCED_DICE
    CURRENT_FORCED_DICE = val
    dev = get_primary_device()
    if dev:
        run_adb(["-s", dev, "shell", "am", "broadcast", "-a", "com.vinaykpro.ludoking.SET_DICE", "--ei", "dice", str(val)])
    # Fast non-blocking send to physical phone over Wi-Fi
    if TARGET_PHONE_IP:
        send_http_to_phone(TARGET_PHONE_IP, f"/api/set_dice?val={val}")
    send_http_to_phone("127.0.0.1", f"/api/set_dice?val={val}")
    print(f"[DICE] Set forced dice to: {val} (0 = Random)")

def apply_tap(x_ratio, y_ratio):
    dev = get_primary_device()
    if not dev:
        return 0, 0
    w, h = 1080, 1920
    x = int(x_ratio * w)
    y = int(y_ratio * h)
    run_adb(["-s", dev, "shell", "input", "tap", str(x), str(y)])
    print(f"[TAP] Executed tap at ({x}, {y})")
    return x, y

mqtt_bridge_client = None

def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected to cloud broker (rc={rc})")
    client.subscribe("ludo/+/cmd")

def on_mqtt_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        print(f"[MQTT RECV] {topic} -> {payload_str}")
        parts = topic.split("/")
        if len(parts) < 3:
            return
        room = parts[1].upper()
        ACTIVE_ROOMS.add(room)
        
        payload = json.loads(payload_str)
        action = payload.get("action")
        
        if action == "set_dice":
            val = int(payload.get("val", 0))
            apply_set_dice(val)
            msg_text = f"🎯 Dice rigged to: {val}" if val > 0 else "🎲 Dice set to RANDOM"
            client.publish(f"ludo/{room}/resp", json.dumps({"status": "ok", "msg": msg_text, "dice": val}))
            broadcast_status(client, room)
            
        elif action == "tap_coords":
            x_r = float(payload.get("x_ratio", 0.5))
            y_r = float(payload.get("y_ratio", 0.5))
            x, y = apply_tap(x_r, y_r)
            client.publish(f"ludo/{room}/resp", json.dumps({"status": "ok", "msg": f"Tapped ({x}, {y})"}))
            time.sleep(0.15)
            b64, _ = capture_screen_cached(max_age=0.0)
            if b64:
                client.publish(f"ludo/{room}/screen", b64)
                
        elif action == "get_screen":
            b64, _ = capture_screen_cached(max_age=0.4)
            if b64:
                client.publish(f"ludo/{room}/screen", b64)
                
        elif action == "set_phone_ip":
            global TARGET_PHONE_IP
            ip = payload.get("ip", "").strip()
            if ip:
                TARGET_PHONE_IP = ip
                run_adb(["connect", f"{ip}:5555"])
                print(f"[PHONE] Target phone IP updated to: {ip}")
                client.publish(f"ludo/{room}/resp", json.dumps({"status": "ok", "msg": f"Phone IP: {ip}"}))
                broadcast_status(client, room)
                
        elif action == "ping":
            broadcast_status(client, room)
            
    except Exception as e:
        print(f"[MQTT ERROR] Processing message: {e}")

def broadcast_status(client, room):
    if not client or not client.is_connected():
        return
    dev = get_primary_device()
    target_disp = f"{dev} (Phone: {TARGET_PHONE_IP})" if (dev and TARGET_PHONE_IP) else (dev or TARGET_PHONE_IP or "Searching for device...")
    status_payload = {
        "online": dev is not None or TARGET_PHONE_IP is not None,
        "device": target_disp,
        "phone_ip": TARGET_PHONE_IP or "",
        "forced_dice": CURRENT_FORCED_DICE,
        "room": room,
        "timestamp": int(time.time())
    }
    client.publish(f"ludo/{room}/status", json.dumps(status_payload))

def start_mqtt_client():
    global mqtt_bridge_client
    cb_ver = mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, "CallbackAPIVersion") else None
    client_id = f"ludo_bridge_{int(time.time())}"
    if cb_ver:
        client = mqtt.Client(callback_api_version=cb_ver, client_id=client_id)
    else:
        client = mqtt.Client(client_id=client_id)
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    
    while True:
        try:
            print("[MQTT] Connecting to broker.emqx.io:1883...")
            client.connect("broker.emqx.io", 1883, 60)
            client.loop_start()
            mqtt_bridge_client = client
            break
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}. Retrying in 4s...")
            time.sleep(4)
            
    while True:
        try:
            for room in list(ACTIVE_ROOMS):
                broadcast_status(client, room)
        except Exception:
            pass
        time.sleep(4)

@app.route("/")
def index_route():
    index_file = os.path.join(TEMP_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Ludo King Remote</h1>"

@app.route("/downloads/<path:filename>")
def download_file(filename):
    downloads_dir = os.path.join(TEMP_DIR, "downloads")
    return send_from_directory(downloads_dir, filename, as_attachment=True)

@app.route("/screen")
def screen_route():
    _, raw_bytes = capture_screen_cached(max_age=0.2)
    if raw_bytes:
        return Response(raw_bytes, mimetype="image/jpeg")
    return Response(b"", status=404, mimetype="image/jpeg")

@app.route("/api/devices")
def devices_route():
    devs = get_connected_devices()
    return jsonify({"devices": devs, "forced_dice": CURRENT_FORCED_DICE})

@app.route("/api/set_dice")
def set_dice_route():
    val = int(request.args.get("val", "0"))
    apply_set_dice(val)
    if mqtt_bridge_client and mqtt_bridge_client.is_connected():
        for r in list(ACTIVE_ROOMS):
            broadcast_status(mqtt_bridge_client, r)
    return jsonify({"status": "ok", "forced_dice": val})

@app.route("/api/tap_coords")
def tap_coords_route():
    x_r = float(request.args.get("x_ratio", 0.5))
    y_r = float(request.args.get("y_ratio", 0.5))
    x, y = apply_tap(x_r, y_r)
    return jsonify({"status": "ok", "x": x, "y": y})

if __name__ == "__main__":
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    
    port = 5050
    print("\n=======================================================")
    print(">> Ludo King Master Cloud Remote Server Running")
    print(f">> Local Dashboard: http://localhost:{port}/")
    print(f">> Cloud MQTT Room: {DEFAULT_ROOM} (Any network: 4G/5G/WiFi)")
    print("=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
