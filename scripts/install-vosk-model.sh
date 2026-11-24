#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/ada-m"
VENV="/opt/ada-m-venv"
MODEL_DIR="$ROOT/models/vosk-model-small-pt-0.3"
ZIP_FILE="/tmp/vosk-model-small-pt-0.3.zip"

echo "===== INSTALANDO VOSK PT-BR ====="
"$VENV/bin/pip" install "vosk==0.3.45"

if [ ! -d "$MODEL_DIR" ]; then
  echo "Baixando modelo pequeno de português brasileiro (aprox. 31 MB)..."
  python3 - "$ZIP_FILE" <<'PY'
import sys
import urllib.request
url = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
urllib.request.urlretrieve(url, sys.argv[1])
print("Download concluído.")
PY
  python3 - "$ZIP_FILE" "$ROOT/models" <<'PY'
import sys
import zipfile
from pathlib import Path
archive = Path(sys.argv[1])
destination = Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as zf:
    zf.extractall(destination)
print("Modelo extraído em", destination)
PY
  rm -f "$ZIP_FILE"
fi

"$VENV/bin/python" - <<'PY'
from pathlib import Path
from vosk import Model, SetLogLevel
SetLogLevel(-1)
path = Path("/opt/ada-m/models/vosk-model-small-pt-0.3")
assert path.is_dir(), f"Modelo não encontrado: {path}"
Model(str(path))
print("Vosk PT-BR carregado e validado.")
PY
