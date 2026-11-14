"""
PESTINHA - ponto de entrada.

Rodar:
    python main.py              passo a passo (primeira vez) e tela de permissões
    python main.py --direto     usa as permissões salvas
    python main.py --sair-em N  fecha sozinho depois de N segundos (para testes)

Dependências em requirements.txt. Pânico: Ctrl + Alt + Shift + B (desliga tudo e continua desligado).
"""

import argparse
import shutil
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pestinha import config
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore
from pestinha.app import PestinhaApp
from pestinha.ui.onboarding import Onboarding
from pestinha.ui.ui import SettingsDialog, face_icon


def apagar_memoria(paths):
    """Apaga memory/ e confirma o resultado; devolve (sucesso, caminhos que falharam)."""
    falhas = []
    if paths.memory.exists():
        shutil.rmtree(paths.memory, onerror=lambda _f, caminho, _e: falhas.append(str(caminho)))
    return not falhas and not paths.memory.exists(), falhas


def main():
    parser = argparse.ArgumentParser(description="Pestinha")
    parser.add_argument("--direto", action="store_true", help="pula a tela inicial")
    parser.add_argument("--sair-em", type=float, default=0.0, help="fecha sozinho após N segundos (teste)")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(face_icon())

    paths = Paths()
    store = SettingsStore(paths)
    perms = store.perms
    if not args.direto:
        first_time = not paths.permissions.exists()
        if first_time and Onboarding(config.load_pet(paths, config.escolher_pet(paths, perms["pet"]))["nome"]).exec() != QDialog.Accepted:
            pass                                    # "Pular" também segue para as permissões
        dialog = SettingsDialog(perms, paths, first_run=True)
        dialog.changed.connect(store.update)        # o diálogo trabalha numa cópia: cada escolha vem por aqui
        apagado = []

        def apagar_tudo():
            sucesso, falhas = apagar_memoria(paths)
            if not sucesso:
                detalhe = f"\n\nArquivos que falharam: {', '.join(falhas)}" if falhas else ""
                QMessageBox.warning(
                    dialog, "Não foi possível apagar tudo",
                    "Alguns dados continuam na pasta memory/. Feche programas que possam estar "
                    f"usando esses arquivos e tente novamente.{detalhe}",
                )
                return
            apagado.append(True)
            dialog.reject()

        dialog.wipe_all.connect(apagar_tudo)
        if dialog.exec() != QDialog.Accepted or apagado:
            return 0
        store.save()                                # grava já: a próxima vez não mostra o passo a passo

    pet_app = PestinhaApp(store, paths)
    if args.sair_em > 0:
        QTimer.singleShot(int(args.sair_em * 1000), pet_app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
