from app.google_search import _extract_grounded_output


def test_extract_grounded_output_reads_text_and_url_citations():
    payload = {
        "steps": [
            {"type": "google_search_call", "arguments": {"queries": ["test"]}},
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": "A informação foi confirmada em fonte oficial.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "Fonte oficial",
                                "url": "https://example.org/source",
                                "start_index": 0,
                                "end_index": 32,
                            }
                        ],
                    }
                ],
            },
        ]
    }
    summary, sources = _extract_grounded_output(payload)
    assert "confirmada" in summary
    assert len(sources) == 1
    assert sources[0]["title"] == "Fonte oficial"
    assert sources[0]["url"] == "https://example.org/source"


def test_extract_grounded_output_rejects_non_http_and_duplicate_urls():
    payload = {
        "steps": [{
            "type": "model_output",
            "content": [{
                "type": "text",
                "text": "Resultado.",
                "annotations": [
                    {"type": "url_citation", "title": "bad", "url": "javascript:alert(1)", "start_index": 0, "end_index": 5},
                    {"type": "url_citation", "title": "one", "url": "https://example.org/a", "start_index": 0, "end_index": 5},
                    {"type": "url_citation", "title": "duplicate", "url": "https://example.org/a", "start_index": 0, "end_index": 5},
                ],
            }],
        }]
    }
    _, sources = _extract_grounded_output(payload)
    assert len(sources) == 1
    assert sources[0]["title"] == "one"


def test_extract_grounded_output_handles_empty_payload():
    assert _extract_grounded_output({}) == ("", [])
