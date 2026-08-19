from seshat.core.history import HistoryEntry, parse_entries, render_gantt, render_history_body


def test_parse_roundtrip():
    body = render_history_body(
        [
            HistoryEntry("2026-08-10", "Segunda decisão", "Resumo dois", "Detalhe dois."),
            HistoryEntry("2026-08-01", "Primeira decisão", "Resumo um", "Detalhe um."),
        ]
    )
    entries = parse_entries(body)
    assert [e.date for e in entries] == ["2026-08-10", "2026-08-01"]
    assert entries[0].summary_line == "Resumo dois"
    assert entries[1].detail == "Detalhe um."


def test_gantt_is_chronological_oldest_first():
    gantt = render_gantt(
        [
            HistoryEntry("2026-08-01", "A", "Resumo A", ""),
            HistoryEntry("2026-08-10", "B", "Resumo B", ""),
        ]
    )
    assert gantt.index("Resumo A") < gantt.index("Resumo B")
    assert "milestone" in gantt


def test_empty_history_not_fabricated():
    body = render_history_body([])
    assert "Sem entradas" in body
    assert "milestone" not in body


def test_mermaid_label_strips_colon():
    gantt = render_gantt([HistoryEntry("2026-08-01", "A", "Resumo: com dois pontos", "")])
    assert "Resumo: com dois pontos" not in gantt
    assert "Resumo - com dois pontos" in gantt
