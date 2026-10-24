#!/bin/bash
# d8 «Wi-Fi» setup. Offline: generate capture.cap + wordlist + brief.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/sq-arsenal/d8"
mkdir -p "$DIR"
python3 -I "$HERE/gen-cap.py" "$DIR/capture.cap" >&2 || true
cat > "$DIR/wordlist.txt" <<'EOF'
123456
password
biscuits
summer2023
letmein
wireless
hunter2
EOF
cat > "$DIR/README.txt" <<'EOF'
Модуль d8 — Wi-Fi (Aircrack-ng), ОФЛАЙН по готовому capture.cap.
  aircrack-ng capture.cap            — ESSID/BSSID, наличие handshake
  aircrack-ng -w wordlist.txt capture.cap — подбор ключа
Учебная записка: сеть ESSID=ARSENAL-LAB; рукопожатие WPA2 присутствует (да);
восстановленный ключ для этого учебного образца = biscuits. В VM нет Wi-Fi-адаптера,
поэтому «живая» часть (monitor mode) недоступна и не требуется для прохождения.
EOF
echo "[dlc/d8] capture.cap + wordlist + brief at $DIR" >&2
exit 0
