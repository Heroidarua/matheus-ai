from __future__ import annotations


def decode_text_bytes(raw: bytes) -> str:
    """Decode common text encodings while rejecting binary-looking content."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp1252")
            except UnicodeDecodeError:
                text = raw.decode("iso-8859-1")

    if not text:
        return text

    controls = sum(1 for char in text if ord(char) < 32 and char not in "\t\n\r\f")
    if controls / max(len(text), 1) > 0.01:
        raise UnicodeError("O conteúdo parece ser binário, não texto.")
    return text
