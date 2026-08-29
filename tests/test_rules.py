"""Tests für regelbasiertes Routing."""

from daemon.router.rules import match_rules


def test_time_query_matches_get_current_time():
    match = match_rules("wie spät ist es")
    assert match is not None
    assert match.tool_name == "get_current_time"


def test_note_prefix_maps_to_write_note():
    match = match_rules("note: Einkaufsliste Milch")
    assert match is not None
    assert match.tool_name == "write_note"
    assert "Milch" in match.tool_args["content"]
