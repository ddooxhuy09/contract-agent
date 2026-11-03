from scripts.audit_status4_provisions import render_markdown, verdict


def _result(with_eff_to: int, relations: dict | None = None) -> dict:
    return {
        "generated_at": "2026-11-03T00:00:00+00:00",
        "provision_relation_counts": relations or {},
        "documents": [
            {
                "doc_id": "1",
                "doc_num": "145/2020/NĐ-CP",
                "status_flag": 4,
                "levels": {
                    "legal_articles": [
                        {"status_flag": 4, "nodes": 10, "with_eff_from": 10, "with_eff_to": with_eff_to}
                    ]
                },
                "chunks_by_is_effective": {"False": 10},
            },
            {
                "doc_id": "2",
                "doc_num": "other",
                "status_flag": 1,
                "levels": {"legal_articles": [{"status_flag": 4, "nodes": 99, "with_eff_from": 0, "with_eff_to": 0}]},
                "chunks_by_is_effective": {},
            },
        ],
    }


def test_verdict_rejects_filter_without_expiry_dates():
    v = verdict(_result(with_eff_to=0, relations={"sua_doi": 1}))
    assert v["status4_nodes"] == 10  # only status-4 documents are counted
    assert v["date_aware_filter_supported"] is False
    assert v["provision_relation_rows"] == 1


def test_verdict_accepts_filter_when_expiry_dates_exist():
    assert verdict(_result(with_eff_to=9))["date_aware_filter_supported"] is True


def test_render_markdown_reports_verdict():
    result = _result(with_eff_to=0)
    result["verdict"] = verdict(result)
    text = render_markdown(result)
    assert "Date-aware status-4 filter supported by the data: **False**" in text
    assert "145/2020/NĐ-CP" in text
