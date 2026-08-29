from daemon.main import HUD_DIR, app


def test_hud_files_exist() -> None:
    assert (HUD_DIR / "index.html").is_file()
    assert (HUD_DIR / "app.js").is_file()
    assert (HUD_DIR / "styles.css").is_file()


def test_hud_routes_registered() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/" in paths
    assert "/api/status" in paths
    assert "/health" in paths
    assert "/styles.css" in paths
    assert "/app.js" in paths
    assert "/api/transcribe" in paths
    assert "/api/tts" in paths
    assert any(
        str(getattr(route, "path", "")).startswith("/static") for route in app.routes
    )
