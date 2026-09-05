# 🎲 Ludo King Pro Suite — Made by Taka

A universal cloud-powered remote controller and live dice rigger for **Ludo King**, created and engineered by **Taka**. Control your match from **any smartphone, tablet, or browser anywhere in the world** (over 4G, 5G, or Wi-Fi) with real-time screen mirroring and tap-to-click controls.

### 📥 [Download Ludo_King_Made_by_Taka.apk (v1.0 / 55.2 MB)](https://github.com/takaisbjehei/ludo-king-remote/releases/download/v1.0.0/Ludo_King_Made_by_Taka.apk)

Hosted directly on **Vercel** with zero backend infrastructure needed in the cloud!

---

## 👨‍💻 Creator & Maintainer
- **Architect & Modder**: **Taka** ([@takaisbjehei](https://github.com/takaisbjehei))
- **Edition**: Ludo King Made by Taka Edition (v8.0.0.x Patched)

---

## 🌟 Key Features

- **🌐 Works from Any Device Anywhere**: Controlled via encrypted MQTT WebSockets (`wss://broker.emqx.io:8084/mqtt`). You don't need to be on the same Wi-Fi network; it works seamlessly over mobile cellular data.
- **🎯 Universal Dice Controller**:
  - Force any roll: `1`, `2`, `3`, `4`, `5`, or `6`.
  - Works for **all players** (Player 1, Player 2, Player 3, Player 4).
  - `🎲 RANDOM` button to instantly return to standard fair dice mechanics.
- **⚡ Quick Roll Shortcuts**:
  - One-tap buttons for Blue (P1), Green (P2), Red (P3), and Yellow (P4).
- **📺 Ultra-Low Latency Live Screen Mirror**:
  - High-performance JPEG streaming at ~25 KB per frame.
  - Interactive tap forwarding: tap anywhere on the screen preview to tap that exact spot in the game on your emulator or phone.
- **🔑 Room Code Pairing**:
  - Connect multiple remotes or share controls using custom room codes (`#LUDO88`, `#MYROOM`, etc.).

---

## 🚀 Getting Started

### 1. Deploy Frontend to Vercel
1. Import this repository into your [Vercel Dashboard](https://vercel.com/new).
2. Click **Deploy** (No custom build settings required, it's a pure high-performance static PWA).
3. Open your deployed Vercel URL on your mobile phone or browser:
   `https://<your-project>.vercel.app/#LUDO88`

---

### 2. Run the PC / Host Bridge
On the computer running your Android emulator (BlueStacks, LDPlayer, Nox) or USB-connected Android phone:

```bash
# 1. Install prerequisites (if not already installed)
pip install paho-mqtt Pillow flask

# 2. Start the bridge
python adb_remote_server.py
```

The bridge will automatically:
- Connect to your Android device via ADB (`127.0.0.1:5555` or USB).
- Connect to the secure cloud broker and pair with room `LUDO88`.
- Expose a local dashboard at `http://localhost:5050/`.

---

## 🎮 How to Play

1. Open the Vercel URL on your phone.
2. Select your desired dice roll (`1` to `6`).
3. Tap the dice in the game (or tap the Quick Roll button on the remote).
4. Watch the chosen number roll every single time!
5. Tap **🎲 RANDOM** anytime to restore regular rolls.

---

## 🛡️ Architecture Overview

```
[ Your Phone / Any Browser (Vercel) ]
             ▲
             │  (MQTT WebSockets wss://broker.emqx.io:8084/mqtt)
             ▼
[ Cloud MQTT Broker (Room: LUDO88) ]
             ▲
             │  (MQTT TCP 1883)
             ▼
[ Host PC Bridge (adb_remote_server.py) ]
             ▲
             │  (ADB / Broadcast Intent)
             ▼
[ Android Device / Emulator (Ludo King) ]
```

---

## 📜 License
MIT License
