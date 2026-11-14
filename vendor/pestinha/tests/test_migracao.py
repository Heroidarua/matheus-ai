"""
Etapa 1 do multipet: memória por pet (memory/pets/<pet>/) e a migração da versão antiga.

Cobre os critérios combinados: cópia validada byte a byte e no formato real (JSON e JSONL),
conflito bloqueia sem sobrescrever, marcador só no fim, interrupção sem perda, legado
recuperável, ids antigos não viram personagens, e isolamento dos oito arquivos entre pets.
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config, migracao  # noqa: E402
from pestinha.paths import Paths, pet_id_valido  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

ARQUIVOS = {
    "episodes.jsonl": b'{"contexto": "IDLE|feliz", "acao": "meme", "valencia": 0.5}\n'
                      b'linha quebrada\n{"contexto": "WORK|curioso", "acao": "nada", "valencia": 0.0}\n',
    "preferences.json": b'{"tabela": {"IDLE|feliz": {"meme": [1, 0.5]}}, "geral": {"meme": [1, 0.5]}}',
    "drives.json": b'{"energy": 0.42, "stimulation": 0.3, "contact": 0.2, "saved_at": 1}',
    "protest.json": b'{"grievance": 0.7, "revolutions": 2, "saved_at": 1}',
    "sad_protest.json": b'{"grievance": 0.1, "revolutions": 0, "saved_at": 1}',
    "conditioning.json": b'{"V": {"PRESS": 0.3, "APPROACH": 0.1, "PLACA": 0.4}}',
    "castigo.json": b'{"vitorias": {"fugir": 3.0}, "rancor": 0.25, "receio": 0.5}',
}


def layout_antigo(tmp_path, extras=True):
    paths = Paths(root=tmp_path)
    paths.memory.mkdir(parents=True)
    for nome, dados in ARQUIVOS.items():
        (paths.memory / nome).write_bytes(dados)
    (paths.memory / "bryan_nervous.json").write_bytes(b'{"version": 1, "seed": 7}')
    if extras:
        (paths.memory / "buddy_nervous.json").write_bytes(b'{"version": 1, "seed": 3}')
        (paths.memory / "permissions.json").write_bytes(b'{"pet": "bryan"}')
        (paths.memory / "timeline.csv").write_bytes(b"minuto,atividade\n")
    return paths


def originais(paths):
    return {p.name: p.read_bytes() for p in paths.memory.iterdir() if p.is_file()}


# ---------------- migração ----------------

def test_migra_tudo_e_confere(tmp_path):
    paths = layout_antigo(tmp_path)
    antes = originais(paths)
    r = migracao.migrar(paths, "bryan")
    assert r.ok and set(r.pets_concluidos) == {"bryan", "buddy"}
    pet_app = paths.pet("bryan")
    for nome, dados in ARQUIVOS.items():
        assert (pet_app.base / nome).read_bytes() == dados
    assert pet_app.nervous.read_bytes() == antes["bryan_nervous.json"]
    assert paths.pet("buddy").nervous.read_bytes() == antes["buddy_nervous.json"]
    for nome in list(ARQUIVOS) + ["bryan_nervous.json"]:
        assert not (paths.memory / nome).exists()
        assert (paths.legado / "bryan" / nome).read_bytes() == antes[nome]
    marcador = json.loads(pet_app.marcador.read_text(encoding="utf-8"))
    assert set(marcador["arquivos"]) == set(ARQUIVOS) | {"nervous.json"}
    # o que é global fica onde estava
    assert (paths.memory / "permissions.json").read_bytes() == antes["permissions.json"]
    assert (paths.memory / "timeline.csv").read_bytes() == antes["timeline.csv"]


def test_segunda_execucao_nao_muda_nada(tmp_path):
    paths = layout_antigo(tmp_path)
    migracao.migrar(paths, "bryan")
    foto = {p: p.read_bytes() for p in paths.memory.rglob("*") if p.is_file()}
    r = migracao.migrar(paths, "bryan")
    assert r.ok and not r.migrados
    assert {p: p.read_bytes() for p in paths.memory.rglob("*") if p.is_file()} == foto


def test_interrupcao_na_copia_retoma_sem_perda(tmp_path, monkeypatch):
    paths = layout_antigo(tmp_path, extras=False)
    antes = originais(paths)
    gravar = migracao._gravar_atomico
    chamadas = []

    def falha_no_quarto(destino, dados):
        chamadas.append(destino)
        if len(chamadas) == 4:
            raise OSError("queda simulada")
        gravar(destino, dados)

    monkeypatch.setattr(migracao, "_gravar_atomico", falha_no_quarto)
    r = migracao.migrar(paths, "bryan")
    assert not r.ok and not paths.pet("bryan").marcador.exists()
    assert originais(paths) == antes                         # nenhum original saiu do lugar
    monkeypatch.setattr(migracao, "_gravar_atomico", gravar)
    assert migracao.migrar(paths, "bryan").ok
    for nome, dados in ARQUIVOS.items():
        assert (paths.pet("bryan").base / nome).read_bytes() == dados


def test_interrupcao_ao_mover_para_o_legado_retoma_sem_perda(tmp_path, monkeypatch):
    paths = layout_antigo(tmp_path, extras=False)
    antes = originais(paths)
    mover = migracao._mover_para_legado
    movidos = []

    def falha_no_segundo(origem, pasta):
        if movidos:
            raise OSError("queda simulada")
        movidos.append(origem)
        return mover(origem, pasta)

    monkeypatch.setattr(migracao, "_mover_para_legado", falha_no_segundo)
    assert not migracao.migrar(paths, "bryan").ok
    assert not paths.pet("bryan").marcador.exists()
    monkeypatch.setattr(migracao, "_mover_para_legado", mover)
    assert migracao.migrar(paths, "bryan").ok
    legado = {p.name: p.read_bytes() for p in (paths.legado / "bryan").iterdir()}
    assert legado == antes                                   # cada original aparece uma vez, igual


def test_conflito_bloqueia_sem_sobrescrever(tmp_path):
    paths = layout_antigo(tmp_path, extras=False)
    antes = originais(paths)
    destino = paths.pet("bryan").drives
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b'{"energy": 0.99}')
    r = migracao.migrar(paths, "bryan")
    assert not r.ok and not r.pet_ok("bryan")
    assert [(p, a) for p, a, _m in r.conflitos] == [("bryan", "drives.json")]
    assert destino.read_bytes() == b'{"energy": 0.99}'          # destino intocado
    assert originais(paths) == antes                           # originais intocados
    assert not paths.pet("bryan").marcador.exists()


def test_formatos_reais_jsonl_e_json_ilegivel(tmp_path):
    paths = layout_antigo(tmp_path, extras=False)
    (paths.memory / "drives.json").write_bytes(b"{isto nao e json")
    r = migracao.migrar(paths, "bryan")
    assert r.ok
    avisos = {a for _p, a, _m in r.avisos}
    assert avisos == {"episodes.jsonl", "drives.json"}         # copiados iguais, com aviso
    assert paths.pet("bryan").drives.read_bytes() == b"{isto nao e json"
    lidos = migracao._ler_formato("episodes.jsonl", paths.pet("bryan").episodes.read_bytes())
    assert len(lidos) == 3 and lidos[0]["acao"] == "meme"     # registro por registro


def test_restaurar_volta_a_estrutura_antiga(tmp_path):
    paths = layout_antigo(tmp_path, extras=False)
    antes = originais(paths)
    migracao.migrar(paths, "bryan")
    devolvidos = migracao.restaurar(paths, "bryan")
    assert set(devolvidos) == set(antes)
    assert originais(paths) == antes
    assert not paths.pet("bryan").marcador.exists()


def test_restaurar_escolhe_a_geracao_mais_recente(tmp_path):
    paths = Paths(root=tmp_path)
    legado = paths.legado / "bryan"
    legado.mkdir(parents=True)
    (legado / "drives.json").write_text('{"versao": "antiga"}', encoding="utf-8")
    (legado / "drives.2.json").write_text('{"versao": "atual"}', encoding="utf-8")

    devolvidos = migracao.restaurar(paths, "bryan")

    assert devolvidos == ["drives.json"]
    assert json.loads((paths.memory / "drives.json").read_text(encoding="utf-8")) == {"versao": "atual"}
    assert (legado / "drives.json").exists()       # a geração anterior continua recuperável
    assert not (paths.memory / "drives.2.json").exists()


def test_ids_antigos_nao_viram_personagens(tmp_path):
    paths = layout_antigo(tmp_path)
    (paths.memory / "bravo_nervous.json").write_bytes(b"{}")
    paths.pets.mkdir()
    (paths.pets / "bryan.json").write_text('{"nome": "Bryan", "seed": 7}', encoding="utf-8")
    migracao.migrar(paths, "bryan")
    assert config.list_pets(paths) == ["bryan"]
    assert paths.pet("bravo").nervous.exists()                 # a memória antiga foi guardada, só não é um pet


def test_id_de_pet_que_vira_pasta_e_validado(tmp_path):
    assert not pet_id_valido("../fora") and not pet_id_valido("") and pet_id_valido("bryan")
    with pytest.raises(ValueError):
        Paths(root=tmp_path).pet("../fora")


# ---------------- no app ----------------

def criar_app(tmp_path, monkeypatch, pet="bryan"):
    QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, pet=pet))
    app = app_mod.PestinhaApp(store, paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    return app


def estado(app):
    return {
        "energia": round(app.drives.energy, 2),
        "vitorias": app.castigo.vitorias["fugir"],
        "rancor": app.castigo.rancor,
        "placa": app.conditioning.V["PLACA"],
        "episodios": len(app.memory.recent),
        "revolucoes": app.protest.revolutions,
        "aprendido": app.brain.learned.copy(),
    }


def mexer(app):
    app.drives.energy = 0.37
    app.castigo.vitorias["fugir"], app.castigo.rancor = 4.0, 0.3
    app.conditioning.V["PLACA"] = 0.6
    app.memory.start("IDLE|feliz", "meme")
    app.memory._resolve(app.memory.open[0], "teste", 0.4)
    app.protest.revolutions = 5
    app.brain.learned[0, 0] = 0.03


def test_bryan_igual_antes_e_depois_da_migracao(tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch)
    mexer(app)
    app.save()
    antes = estado(app)
    paths = app.paths
    novo, antigo = paths.pet("bryan"), paths.pet_legado("bryan")
    for de, para in zip(novo.todos(), antigo.todos()):         # monta o formato da versão antiga
        de.replace(para)
    assert antigo.drives.exists() and antigo.nervous.name == "bryan_nervous.json"
    depois = estado(criar_app(tmp_path, monkeypatch))
    assert (depois["aprendido"] == antes.pop("aprendido")).all()
    depois.pop("aprendido")
    assert depois == antes
    assert paths.pet("bryan").marcador.exists()


def test_migracao_pendente_usa_modo_compativel(tmp_path, monkeypatch):
    paths = layout_antigo(tmp_path, extras=False)
    paths.pet("bryan").base.mkdir(parents=True)
    paths.pet("bryan").drives.write_bytes(b'{"energy": 0.99}')   # conflito
    app = criar_app(tmp_path, monkeypatch)
    assert app.pet_paths.base == paths.memory and app.aviso_migracao
    assert app.castigo.vitorias["fugir"] == 3.0                   # leu os arquivos antigos
    assert app.conditioning.V["PLACA"] == pytest.approx(0.4)


def test_sem_permissao_de_escrita_nao_derruba_e_nao_perde(tmp_path, monkeypatch):
    paths = layout_antigo(tmp_path, extras=False)
    antes = originais(paths)
    monkeypatch.setattr(migracao, "_gravar_atomico", Mock(side_effect=PermissionError("somente leitura")))
    app = criar_app(tmp_path, monkeypatch)
    assert app.pet_paths.base == paths.memory and app.aviso_migracao
    assert "8 arquivos" in app.aviso_migracao and app.aviso_migracao.count("somente leitura") == 1
    assert {n: d for n, d in originais(paths).items() if n in antes} == antes


def test_pets_nao_compartilham_memoria(tmp_path, monkeypatch):
    (tmp_path / "pets").mkdir()
    (tmp_path / "pets" / "teste.json").write_text('{"nome": "Teste", "seed": 99}', encoding="utf-8")
    (tmp_path / "pets" / "bryan.json").write_text('{"nome": "Bryan", "seed": 7}', encoding="utf-8")
    pet_app = criar_app(tmp_path, monkeypatch, "bryan")
    mexer(pet_app)
    pet_app.save()
    estado_bryan = estado(pet_app)
    arquivos_bryan = {p: p.read_bytes() for p in pet_app.pet_paths.todos() if p.exists()}
    assert len(arquivos_bryan) == 8

    outro = criar_app(tmp_path, monkeypatch, "teste")
    inicial = estado(outro)
    assert inicial["vitorias"] == 0 and inicial["placa"] == 0 and inicial["episodios"] == 0
    assert inicial["revolucoes"] == 0 and inicial["rancor"] == 0 and not inicial["aprendido"].any()
    mexer(outro)
    outro.castigo.vitorias["fugir"] = 9.0
    outro.save()
    assert all(p.exists() for p in outro.pet_paths.todos())
    assert set(outro.pet_paths.todos()).isdisjoint(arquivos_bryan)

    assert {p: p.read_bytes() for p in arquivos_bryan} == arquivos_bryan     # Bryan intocado
    de_volta = estado(criar_app(tmp_path, monkeypatch, "bryan"))
    assert (de_volta.pop("aprendido") == estado_bryan.pop("aprendido")).all()
    assert de_volta == estado_bryan


def test_nenhum_caminho_de_memoria_montado_fora_de_paths():
    fora = []
    for arquivo in (ROOT / "pestinha").rglob("*.py"):
        if arquivo.name in ("paths.py", "migracao.py"):
            continue
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"memory\s*/\s*[\"']|\.memory\s*/", linha):
                fora.append(f"{arquivo.name}:{n}")
    assert fora == []
