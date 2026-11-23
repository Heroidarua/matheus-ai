#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/ada-m"
TTS_ROOT="/opt/ada-m-tts"
ENGINE_DIR="$TTS_ROOT/engine"
ENV_FILE="/etc/ada-m-tts.env"
APP_ENV="$APP_ROOT/.env"
SERVICE_NAME="ada-m-tts.service"
VOICE_REPO="https://github.com/Haple/tiny-voca-ptbr-kokoro.git"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute como root: sudo bash voice-tts/install-vps.sh" >&2
  exit 1
fi

if [[ ! -f "$APP_ENV" ]]; then
  echo "Arquivo $APP_ENV não encontrado. Nada foi alterado." >&2
  exit 1
fi

echo "==> Instalando dependências do sistema"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git espeak-ng python3-venv python3-pip curl openssl

ESPEAK_VERSION="$(espeak-ng --version 2>&1 | sed -n 's/.*text-to-speech: *\([^ ]*\).*/\1/p' | head -n1)"
if [[ "$ESPEAK_VERSION" != "1.51" ]]; then
  echo "AVISO: eSpeak NG $ESPEAK_VERSION detectado; o modelo foi treinado com 1.51."
  echo "A voz pode pronunciar algumas palavras de forma diferente."
fi

if ! id ada-tts >/dev/null 2>&1; then
  useradd --system --home-dir "$TTS_ROOT" --create-home --shell /usr/sbin/nologin ada-tts
fi

install -d -o ada-tts -g ada-tts -m 0750 "$TTS_ROOT"

if [[ ! -d "$ENGINE_DIR/.git" ]]; then
  if [[ -e "$ENGINE_DIR" ]]; then
    echo "O caminho $ENGINE_DIR existe e não é um clone Git. Não será sobrescrito." >&2
    exit 1
  fi
  git clone --depth 1 "$VOICE_REPO" "$ENGINE_DIR"
fi

install -o root -g ada-tts -m 0640 "$SCRIPT_DIR/app.py" "$TTS_ROOT/app.py"
chown -R ada-tts:ada-tts "$ENGINE_DIR"

if [[ ! -x "$TTS_ROOT/.venv/bin/python" ]]; then
  python3 -m venv "$TTS_ROOT/.venv"
fi

echo "==> Instalando runtime ONNX e API (CPU)"
"$TTS_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$TTS_ROOT/.venv/bin/python" -m pip install -r "$ENGINE_DIR/requirements.txt"
"$TTS_ROOT/.venv/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
chown -R ada-tts:ada-tts "$TTS_ROOT"

if [[ ! -s "$ENV_FILE" ]] || ! grep -q '^TTS_API_KEY=.' "$ENV_FILE"; then
  umask 077
  printf 'TTS_API_KEY=%s\n' "$(openssl rand -hex 32)" > "$ENV_FILE"
fi
chown root:root "$ENV_FILE"
chmod 0600 "$ENV_FILE"
TTS_API_KEY="$(sed -n 's/^TTS_API_KEY=//p' "$ENV_FILE" | head -n1)"
if [[ -z "$TTS_API_KEY" ]]; then
  echo "Não foi possível obter a chave do serviço TTS." >&2
  exit 1
fi
export TTS_API_KEY

install -o root -g root -m 0644 "$SCRIPT_DIR/ada-m-tts.service" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo "==> Aguardando o serviço local de voz"
python3 - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:8002"
for attempt in range(40):
    try:
        with urllib.request.urlopen(base + "/health", timeout=3) as response:
            data = json.loads(response.read())
        if data.get("ready") and data.get("status") == "ok":
            print("TTS local pronto:", data)
            break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("O serviço TTS não ficou pronto. Consulte: journalctl -u ada-m-tts.service -n 80")

payload = json.dumps({
    "model": "tiny-voca-ptbr",
    "input": "Olá! Eu sou a ADA-M. Esta é a minha voz em português brasileiro.",
    "voice": "F",
    "response_format": "wav",
    "speed": 1.0,
}).encode()
request = urllib.request.Request(
    base + "/v1/audio/speech",
    data=payload,
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["TTS_API_KEY"],
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=45) as response:
    audio = response.read()
    if response.headers.get_content_type() != "audio/wav" or not audio.startswith(b"RIFF"):
        raise SystemExit("O serviço respondeu, mas o WAV de teste é inválido.")
with open("/tmp/ada-m-tts-check.wav", "wb") as output:
    output.write(audio)
print(f"Áudio de teste válido: {len(audio)} bytes (/tmp/ada-m-tts-check.wav)")
PY

echo "==> Configurando o proxy TTS da ADA-M"
STAMP="$(date +%Y%m%d-%H%M%S)"
APP_ENV_BACKUP="$APP_ENV.before-tiny-voca-$STAMP"
cp -a "$APP_ENV" "$APP_ENV_BACKUP"

python3 - "$APP_ENV" "$TTS_API_KEY" <<'PY'
from pathlib import Path
import os
import re
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
original_stat = path.stat()
lines = path.read_text(encoding="utf-8").splitlines()
values = {
    "TTS_API_URL": "http://127.0.0.1:8002",
    "TTS_API_KEY": key,
    "TTS_VOICE": "F",
    "TTS_ENGINE": "tiny-voca-ptbr",
}
for name, value in values.items():
    pattern = re.compile(rf"^{re.escape(name)}=")
    matches = [i for i, line in enumerate(lines) if pattern.match(line)]
    if matches:
        first = matches[0]
        lines[first] = f"{name}={value}"
        for index in reversed(matches[1:]):
            del lines[index]
    else:
        lines.append(f"{name}={value}")

temporary = path.with_name(path.name + ".tmp")
temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(temporary, original_stat.st_mode & 0o777)
os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
os.replace(temporary, path)
print("Configuração local adicionada; chave não exibida.")
PY

echo "==> Reiniciando ADA-M"
systemctl restart ada-m.service
for attempt in $(seq 1 30); do
  if curl --max-time 2 -fsS http://127.0.0.1:8001/health >/dev/null; then
    echo "ADA-M respondeu HTTP 200."
    break
  fi
  sleep 2
done

if ! curl --max-time 5 -fsS http://127.0.0.1:8001/health >/dev/null; then
  echo "A ADA-M não respondeu após a configuração. Restaurando o .env anterior." >&2
  cp -a "$APP_ENV_BACKUP" "$APP_ENV"
  systemctl restart ada-m.service || true
  exit 1
fi

echo
echo "INSTALAÇÃO CONCLUÍDA"
echo "Serviço TTS: $(systemctl is-active "$SERVICE_NAME")"
echo "API TTS: http://127.0.0.1:8002 (somente localhost)"
echo "Backup do ambiente ADA-M: $APP_ENV_BACKUP"
echo "Áudio de teste: /tmp/ada-m-tts-check.wav"
echo "Verifique: journalctl -u ada-m-tts.service -n 50 --no-pager"
