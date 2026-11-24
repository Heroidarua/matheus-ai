#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/ada-m"
SOURCE="/opt/whisper.cpp"
MODEL_DIR="$ROOT/models"
MODEL="$MODEL_DIR/ggml-base-q5_1.bin"
CLI="/usr/local/bin/whisper-cli"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute como root: sudo bash scripts/install-whisper-cpp.sh" >&2
  exit 1
fi

echo "===== INSTALANDO WHISPER.CPP CPU ====="
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential cmake git curl ca-certificates

if [[ ! -d "$SOURCE/.git" ]]; then
  if [[ -e "$SOURCE" ]]; then
    echo "O caminho $SOURCE existe e não é um clone Git. Não será sobrescrito." >&2
    exit 1
  fi
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$SOURCE"
else
  git -C "$SOURCE" pull --ff-only
fi

echo "Compilando whisper-cli com um único job para reduzir o pico de RAM..."
cmake -S "$SOURCE" -B "$SOURCE/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON \
  -DGGML_NATIVE=OFF
cmake --build "$SOURCE/build" --config Release --target whisper-cli -j1

if [[ ! -x "$SOURCE/build/bin/whisper-cli" ]]; then
  echo "O binário whisper-cli não foi encontrado após a compilação." >&2
  exit 1
fi
install -o root -g root -m 0755 "$SOURCE/build/bin/whisper-cli" "$CLI"

install -d -o root -g root -m 0755 "$MODEL_DIR"
if [[ ! -s "$MODEL" ]]; then
  echo "Baixando modelo multilíngue Base quantizado Q5_1..."
  curl -fL --retry 3 --retry-delay 2 \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin?download=true" \
    -o "$MODEL.tmp"
  if [[ "$(stat -c %s "$MODEL.tmp")" -lt 30000000 ]]; then
    rm -f "$MODEL.tmp"
    echo "O arquivo baixado parece incompleto ou inválido." >&2
    exit 1
  fi
  echo "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898  $MODEL.tmp" | sha256sum -c -
  mv "$MODEL.tmp" "$MODEL"
  chmod 0644 "$MODEL"
fi

echo "Validando binário e carregamento do modelo..."
"$CLI" --help >/dev/null
python3 - <<'PY'
import wave
with wave.open("/tmp/ada-whisper-check.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(16000)
    f.writeframes(b"\x00\x00" * 16000)
PY
"$CLI" -m "$MODEL" -f /tmp/ada-whisper-check.wav -l pt -t 2 -nt -np >/tmp/ada-whisper-check.txt
rm -f /tmp/ada-whisper-check.wav /tmp/ada-whisper-check.txt

echo
echo "Whisper.cpp instalado e validado."
echo "Binário: $CLI"
echo "Modelo: $MODEL"
echo "Backend padrão: whisper_cpp (Vosk permanece disponível para rollback)."
