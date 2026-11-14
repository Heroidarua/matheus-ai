"""Robustez: arquivo corrompido, assets faltando, log em arquivo. Rodar: python -m pytest tests -q"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha import config  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.store import read_json, write_json  # noqa: E402


def test_arquivo_corrompido_vira_copia_e_volta_padrao(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{nao e json", encoding="utf-8")
    assert read_json(p, default={"a": 1}) == {"a": 1}
    assert not p.exists()
    assert (tmp_path / "x.json.corrompido").exists()


def test_escrita_e_leitura_ida_e_volta(tmp_path):
    p = tmp_path / "sub" / "y.json"
    write_json(p, {"oi": "olá"})
    assert read_json(p) == {"oi": "olá"}


def test_checagem_de_assets_avisa_o_que_falta(tmp_path):
    warnings = config.check_assets(Paths(root=tmp_path).conteudo("bryan"))
    assert any("memes" in w for w in warnings)
    assert any("recadinhos" in w for w in warnings)


def test_log_grava_em_arquivo(tmp_path):
    from pestinha import log as log_module
    f = tmp_path / "buddy.log"
    log_module.setup(f)
    log_module.log("mensagem de teste")
    assert "mensagem de teste" in f.read_text(encoding="utf-8")
