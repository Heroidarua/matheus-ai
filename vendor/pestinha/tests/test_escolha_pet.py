"""
Etapa 3 do multipet: escolha do personagem nas configurações e o nome certo em cada texto.

O programa se chama Pestinha (config.APP_NOME); quem fala nos textos é o pet escolhido.
Trocar de pet só grava a escolha: vale ao reabrir, cada um com a própria memória e conteúdo.
"""
import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.core.protesto import DEFAULT_SIGNS  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


def dois_pets(tmp_path):
    paths = Paths(root=tmp_path)
    paths.pets.mkdir()
    paths.definicao("bryan").write_text('{"nome": "Bryan", "seed": 7}', encoding="utf-8")
    paths.definicao("teste").write_text('{"nome": "Teste", "seed": 99}', encoding="utf-8")
    (paths.pets / "bryan").mkdir()
    (paths.pets / "bryan" / "recadinhos.txt").write_text("SÓ DO BRYAN\n", encoding="utf-8")
    (paths.pets / "bryan" / "cartazes.txt").write_text("[castigo]\nSÓ DO BRYAN\n", encoding="utf-8")
    return paths


def abrir(paths, monkeypatch, store=None):
    QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    app = app_mod.PestinhaApp(store or SettingsStore(paths), paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    return app


def dialogo(paths, perms, first_run=False):
    QApplication.instance() or QApplication([])
    from pestinha.ui.ui import SettingsDialog
    return SettingsDialog(perms, paths, first_run=first_run)


# ---------------- escolha ----------------

def test_lista_mostra_nomes_e_so_pets_de_verdade(tmp_path):
    paths = dois_pets(tmp_path)
    (paths.memoria_dos_pets / "buddy").mkdir(parents=True)             # memória antiga não é personagem
    (paths.legado / "bravo").mkdir(parents=True)
    paths.definicao("bryan").with_name("Nome Ruim.json").write_text("{}", encoding="utf-8")
    d = dialogo(paths, dict(config.DEFAULT_PERMISSIONS))
    opcoes = [(d.pet_combo.itemText(i), d.pet_combo.itemData(i)) for i in range(d.pet_combo.count())]
    assert opcoes == [("Bryan", "bryan"), ("Teste", "teste")]
    assert d.pet_combo.isEnabled() and d.pet_aviso.isVisibleTo(d)        # dá para trocar com ele aberto


def test_escolher_grava_so_o_pet(tmp_path):
    paths = dois_pets(tmp_path)
    store = SettingsStore(paths)
    antes = dict(store.perms)
    d = dialogo(paths, store.perms)
    mudancas = []
    d.changed.connect(mudancas.append)
    d.changed.connect(store.update)
    d.pet_combo.setCurrentIndex(d.pet_combo.findData("teste"))
    assert mudancas == [{"pet": "teste"}]
    salvo = json.loads(paths.permissions.read_text(encoding="utf-8"))
    assert salvo == dict(antes, pet="teste")
    assert "Conteúdo de Teste" in d.resumo.text()


def test_troca_vale_ao_reabrir(tmp_path, monkeypatch):
    paths = dois_pets(tmp_path)
    store = SettingsStore(paths)
    app = abrir(paths, monkeypatch, store)
    assert app.nome == "Bryan"
    store.update({"pet": "teste"})                                        # escolhido nas configurações
    app.save()
    assert app.nome == "Bryan" and app.pet_paths == paths.pet("bryan")    # o que está na tela continua
    novo = abrir(paths, monkeypatch)
    assert novo.nome == "Teste" and novo.pet_paths == paths.pet("teste")


def test_pet_salvo_que_nao_existe_volta_ao_padrao(tmp_path):
    paths = dois_pets(tmp_path)
    assert config.escolher_pet(paths, "buddy") == "bryan"                 # só memória antiga: não é pet
    assert config.escolher_pet(paths, "../x") == "bryan"
    assert config.escolher_pet(paths, "teste") == "teste"
    paths.definicao("bryan").unlink()
    assert config.escolher_pet(paths, "bryan") == "teste"


def test_nome_sem_definir_vem_do_id(tmp_path):
    paths = Paths(root=tmp_path)
    paths.pets.mkdir()
    paths.definicao("jorge").write_text('{"seed": 3}', encoding="utf-8")
    assert config.load_pet(paths, "jorge")["nome"] == "Jorge"


# ---------------- nomes nos textos ----------------

def test_nome_do_pet_e_do_programa_nos_lugares_certos(tmp_path, monkeypatch):
    paths = dois_pets(tmp_path)
    SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet="teste"))
    app = abrir(paths, monkeypatch)
    assert app.tray.icon.toolTip().startswith("Pestinha · Teste")
    from pestinha.ui.monitor import NeuralMonitor
    from pestinha.ui.panel import StrikePanel
    from pestinha.world.notebook import Notebook
    assert Notebook(app).windowTitle() == "Notebook do Teste"
    assert NeuralMonitor(app, (0, 0)).windowTitle().startswith("Teste ·")
    assert StrikePanel(app, (0, 0)).windowTitle().startswith("Teste ·")
    d = dialogo(paths, app.perms)
    assert d.windowTitle() == "Pestinha" and d.active_box.text() == "Pestinha ligado"


def test_apresentacao_usa_o_nome_do_pet():
    QApplication.instance() or QApplication([])
    from pestinha.ui.onboarding import Onboarding
    o = Onboarding("Teste")
    textos = [o.stack.widget(i).text() for i in range(o.stack.count())]
    assert any("eu sou o Teste" in t for t in textos)
    assert not any("Bryan" in t for t in textos)
    assert o.windowTitle().startswith("Pestinha")


def test_nenhum_texto_visivel_chama_o_pet_de_bryan_no_codigo():
    """Nome de personagem vem do pets/<pet>.json; no código só em comentário, docstring ou log."""
    achados = []
    for arquivo in list((ROOT / "pestinha").rglob("*.py")) + [ROOT / "main.py"]:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(arvore)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                      and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        de_log = {id(c) for n in ast.walk(arvore)
                  if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "log"
                  for c in ast.walk(n)}
        for n in ast.walk(arvore):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str) and "Bryan" in n.value
                    and id(n) not in docstrings and id(n) not in de_log):
                achados.append(f"{arquivo.name}:{n.lineno}: {n.value[:50]}")
    assert achados == []


# ---------------- isolamento completo, trocando pelas configurações ----------------

def test_seis_passos_de_isolamento(tmp_path, monkeypatch):
    paths = dois_pets(tmp_path)
    store = SettingsStore(paths)
    # 1) Bryan gera memória
    pet_app = abrir(paths, monkeypatch, store)
    pet_app.castigo.vitorias["fugir"], pet_app.castigo.rancor = 5.0, 0.4
    pet_app.conditioning.V["PLACA"] = 0.7
    pet_app.drives.energy = 0.33
    pet_app.memory.start("IDLE|feliz", "meme")
    pet_app.memory._resolve(pet_app.memory.open[0], "teste", 0.5)
    pet_app.protest.revolutions = 3
    pet_app.brain.learned[0, 0] = 0.05
    pet_app.save()
    arquivos_bryan = {p: p.read_bytes() for p in pet_app.pet_paths.todos()}
    # 2) fecha e escolhe o outro
    store.update({"pet": "teste"})
    # 3) o outro começa do zero, sem frases nem cartazes do Bryan
    teste = abrir(paths, monkeypatch, SettingsStore(paths))
    assert teste.nome == "Teste"
    assert teste.castigo.vitorias["fugir"] == 0 and teste.castigo.rancor == 0
    assert teste.conditioning.V["PLACA"] == 0 and len(teste.memory.recent) == 0
    assert teste.protest.revolutions == 0 and not teste.brain.learned.any()
    assert teste.mischief.notes.pick() is None and teste.castigo.cartazes == tuple(DEFAULT_SIGNS["castigo"])
    # 4) o outro gera memória própria
    teste.castigo.vitorias["fugir"] = 9.0
    teste.conditioning.V["PLACA"] = 0.1
    teste.save()
    assert set(teste.pet_paths.todos()).isdisjoint(arquivos_bryan)
    # 5) volta ao Bryan: tudo como ele deixou
    store = SettingsStore(paths)
    store.update({"pet": "bryan"})
    assert {p: p.read_bytes() for p in arquivos_bryan} == arquivos_bryan
    de_volta = abrir(paths, monkeypatch, store)
    assert de_volta.castigo.vitorias["fugir"] == 5.0 and de_volta.castigo.rancor == 0.4
    assert de_volta.conditioning.V["PLACA"] == 0.7 and de_volta.protest.revolutions == 3
    assert len(de_volta.memory.recent) == 1 and de_volta.brain.learned[0, 0] == 0.05
    # 6) cada um com o próprio conteúdo
    assert de_volta.mischief.notes.pick() == "SÓ DO BRYAN" and de_volta.castigo.cartazes == ("SÓ DO BRYAN",)
