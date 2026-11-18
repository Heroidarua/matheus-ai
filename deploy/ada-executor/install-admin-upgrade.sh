#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute como root."
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/opt/ada-executor"
ADMIN_PATH="/usr/local/sbin/ada-admin"
SERVICE="ada-executor.service"
BACKUP_DIR="/root/ada-executor-backups/$(date -u +%Y%m%dT%H%M%SZ)"

for file in "$SCRIPT_DIR/admin_routes.py" "$SCRIPT_DIR/ada-admin"; do
  if [[ ! -f "$file" ]]; then
    echo "Arquivo necessário não encontrado: $file"
    exit 1
  fi
done
if [[ ! -f "$APP_DIR/main.py" || ! -x "$APP_DIR/venv/bin/python" ]]; then
  echo "Instalação existente do executor não encontrada em $APP_DIR."
  exit 1
fi
if ! id ada >/dev/null 2>&1; then
  echo "Usuário de serviço 'ada' não encontrado."
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -a "$APP_DIR/main.py" "$BACKUP_DIR/main.py"
if [[ -e "$ADMIN_PATH" ]]; then cp -a "$ADMIN_PATH" "$BACKUP_DIR/ada-admin"; fi
if [[ -e "$APP_DIR/admin_routes.py" ]]; then cp -a "$APP_DIR/admin_routes.py" "$BACKUP_DIR/admin_routes.py"; fi

rollback() {
  local status="$1"
  echo "Falha na atualização; restaurando os arquivos anteriores..."
  cp -a "$BACKUP_DIR/main.py" "$APP_DIR/main.py"
  if [[ -e "$BACKUP_DIR/ada-admin" ]]; then
    cp -a "$BACKUP_DIR/ada-admin" "$ADMIN_PATH"
  fi
  if [[ -e "$BACKUP_DIR/admin_routes.py" ]]; then
    cp -a "$BACKUP_DIR/admin_routes.py" "$APP_DIR/admin_routes.py"
  else
    rm -f "$APP_DIR/admin_routes.py"
  fi
  systemctl restart "$SERVICE" || true
  exit "$status"
}

install -o root -g ada -m 0640 "$SCRIPT_DIR/admin_routes.py" "$APP_DIR/admin_routes.py"
install -o root -g root -m 0750 "$SCRIPT_DIR/ada-admin" "$ADMIN_PATH"

if ! python3 - "$APP_DIR/main.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
marker = "\ndef sse_event("
insertion = (
    "\n\n# Rotas administrativas fixas e somente leitura da ADA-M.\n"
    "from admin_routes import create_admin_router\n"
    "app.include_router(create_admin_router(valid_token))\n"
)
if "create_admin_router(valid_token)" not in source:
    if source.count(marker) != 1:
        print("Não foi possível identificar com segurança o ponto de integração em main.py.")
        raise SystemExit(2)
    source = source.replace(marker, insertion + marker, 1)
path.write_text(source, encoding="utf-8")
PY
then
  rollback 1
fi

chown ada:ada "$APP_DIR/main.py"
if ! "$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/main.py" "$APP_DIR/admin_routes.py"; then
  rollback 1
fi
if ! bash -n "$ADMIN_PATH"; then
  rollback 1
fi
if ! systemctl restart "$SERVICE"; then
  rollback 1
fi

healthy=0
for _ in $(seq 1 15); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" -ne 1 ]]; then
  echo "O health check falhou após a atualização."
  rollback 1
fi

echo "Atualização concluída. Backup: $BACKUP_DIR"
echo "Novas rotas: GET /admin/diagnostics e GET /admin/install-tools/status"
