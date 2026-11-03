from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pestinha_original_source_and_license_are_vendored():
    source = ROOT / "vendor" / "pestinha"
    assert (source / "LICENSE").is_file()
    assert (source / "main.py").is_file()
    assert (source / "pestinha" / "core").is_dir()
    assert (source / "tests").is_dir()
    assert (source / "pets" / "bryan.json").is_file()
    assert (source / "pets" / "jorge.json").is_file()


def test_web_companion_has_both_characters_and_original_meme_assets():
    script = (ROOT / "static" / "pestinha.js").read_text(encoding="utf-8")
    assert "Bryan" in script
    assert "Jorge" in script
    assert "/static/pestinha/pets/" in script
    assert (ROOT / "static" / "pestinha" / "pets" / "bryan" / "memes" / "feliz" / "feliz_10.webp").is_file()
    assert (ROOT / "static" / "pestinha" / "pets" / "jorge" / "memes" / "feliz" / "jorge_feliz_01.webp").is_file()
