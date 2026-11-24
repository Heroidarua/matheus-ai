from app.news_metadata import extract_article_metadata


def test_article_metadata_prefers_published_date_and_checks_feed_consistency():
    html = """
    <html><head>
      <meta property="og:site_name" content="Jornal Exemplo">
      <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"NewsArticle",
         "headline":"Brasil anuncia política de IA",
         "datePublished":"2026-11-19T09:30:00-03:00",
         "author":{"@type":"Person","name":"Ana Repórter"},
         "publisher":{"@type":"Organization","name":"Jornal Exemplo"}}
      </script>
    </head><body><h1>Brasil anuncia política de IA</h1>
      <time datetime="2026-11-19T09:30:00-03:00">19 de novembro de 2026</time>
      <p>Reportagem sobre inteligência artificial.</p>
    </body></html>
    """
    data = extract_article_metadata(
        html, "https://jornalexemplo.com.br/noticia/ia",
        feed_date="2026-11-19",
    )
    assert data["published_date"] == "2026-11-19"
    assert data["published_date_source"] == "datePublished (JSON-LD)"
    assert data["date_status"] == "confirmada"
    assert data["editorial_type"] == "jornalismo"
    assert data["publisher"] == "Jornal Exemplo"
    assert data["author"] == "Ana Repórter"


def test_article_metadata_flags_feed_date_that_disagrees_with_page():
    html = """
    <html><head><script type="application/ld+json">
      {"@type":"NewsArticle","datePublished":"2026-11-19T10:00:00-03:00"}
    </script></head><body><h1>Notícia</h1>
    <time datetime="2026-11-19T10:00:00-03:00">19 de novembro de 2026</time>
    </body></html>
    """
    data = extract_article_metadata(
        html, "https://example.com/noticia",
        feed_date="2026-10-19",
    )
    assert data["published_date"] == "2026-11-19"
    assert data["date_status"] == "divergente_do_feed"


def test_article_metadata_flags_conflicting_visible_and_structured_dates():
    html = """
    <html><head><script type="application/ld+json">
      {"@type":"NewsArticle","datePublished":"2026-11-19"}
    </script></head><body>
      <h1>Notícia</h1><time datetime="2026-11-20">20 de novembro de 2026</time>
    </body></html>
    """
    data = extract_article_metadata(html, "https://example.com/noticia")
    assert data["date_status"] == "conflito_na_pagina"


def test_article_metadata_marks_sponsored_content():
    html = """
    <html><head><meta property="og:site_name" content="Portal Exemplo"></head>
    <body><h1>Empresa anuncia solução de IA</h1>
    <p>Conteúdo patrocinado. Conheça a solução da empresa.</p></body></html>
    """
    data = extract_article_metadata(html, "https://example.com/conteudo")
    assert data["editorial_type"] == "patrocinado"
    assert data["editorial_label"] == "Conteúdo patrocinado / publieditorial"


def test_article_metadata_marks_dino_as_corporate_distribution():
    html = """
    <html><head><meta property="og:site_name" content="Estado Exemplo"></head>
    <body><h1>Uso de IA cresce nas empresas</h1>
    <p>Mundo Corporativo. Conteúdo distribuído pela Agência Dino.</p></body></html>
    """
    data = extract_article_metadata(html, "https://example.com/mundo-corporativo/ia")
    assert data["editorial_type"] == "corporativo"
    assert data["original_source_name"] == "Agência Dino"


def test_article_metadata_identifies_syndicated_agency_and_external_canonical():
    html = """
    <html><head>
      <link rel="canonical" href="https://agenciabrasil.ebc.com.br/geral/noticia/2026-11/ia">
      <meta property="og:site_name" content="Portal Local">
    </head><body><h1>Brasil discute inteligência artificial</h1>
    <p>Com informações da Agência Brasil.</p></body></html>
    """
    data = extract_article_metadata(html, "https://portallocal.com.br/noticia/ia")
    assert data["editorial_type"] == "republicado"
    assert data["original_source_name"] == "agência brasil"
    assert data["original_source_url"] == "https://agenciabrasil.ebc.com.br/geral/noticia/2026-11/ia"


def test_article_metadata_keeps_feed_date_unverified_when_page_has_no_date():
    html = "<html><body><h1>Notícia</h1><p>Texto jornalístico.</p></body></html>"
    data = extract_article_metadata(
        html, "https://example.com/noticia",
        feed_date="2026-11-19",
    )
    assert data["published_date"] == ""
    assert data["feed_published_date"] == "2026-11-19"
    assert data["date_status"] == "somente_feed"
