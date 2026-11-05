"""Edition isolation, themed GUI policy, and sound selection without Qt or network."""
from __future__ import annotations

from pathlib import Path
import pytest
from strapman.core import DEFAULT_SETTINGS, app_directory
from strapman.editions import (BOOTLEGGER, LITE, PRO_THEMES, SOUND_EVENTS,
    active_edition, audio_path, display_name, edition_stylesheet, icon_path,
    normalize_theme)


def test_lite_default_and_untrusted_edition():
    assert active_edition({}) == LITE
    assert active_edition({"STRAPMAN_EDITION": "invalid"}) == LITE
    assert active_edition({"STRAPMAN_EDITION": "  BOOTLEGGER "}) == BOOTLEGGER
    assert display_name(LITE) == "Strapman Lite"
    assert display_name(BOOTLEGGER) == "Bootlegger Pro"


def test_pro_theme_choices_and_lite_isolation():
    css = "QMainWindow { background: navy; }"
    assert edition_stylesheet(css, edition=LITE, theme="Pink Pearl") == css
    assert normalize_theme("Pink Pearl", LITE) == "Retro Dark"
    for label, marker in (("Purple Night", "#0a0510"),
                          ("Pink Pearl", "#fff5fb"),
                          ("Blue Frost", "#f2f9ff")):
        out = edition_stylesheet(css, edition=BOOTLEGGER, theme=label)
        assert marker in out
        assert "QPushButton#primary" in out
    assert len(PRO_THEMES) == 3
    assert normalize_theme("danger", BOOTLEGGER) == "Purple Night"


def test_pro_sound_uses_edition_assets_only():
    base = Path("/checkout")
    for event, filename in SOUND_EVENTS.items():
        assert audio_path(base, event, LITE) is None
        assert audio_path(base, event, BOOTLEGGER) == base / "bootlegger" / "assets" / "sounds" / filename
    with pytest.raises(ValueError):
        audio_path(base, "undefined", BOOTLEGGER)


def test_distinct_icons_and_launchers():
    base = Path(__file__).resolve().parents[1]
    assert icon_path(base, LITE).is_file()
    assert icon_path(base, BOOTLEGGER).is_file()
    for folder, basename in (("lite", "Strapman-Lite"), ("bootlegger", "Bootlegger-Pro")):
        assert (base / folder / f"{basename}.cmd").exists()
        assert (base / folder / f"{basename}.sh").exists()


def test_bootlegger_windows_ico_is_complete_and_multiresolution():
    import struct

    root = Path(__file__).resolve().parents[1]
    data = (root / "bootlegger" / "assets" / "bootlegger-icon.ico").read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", data)
    assert (reserved, image_type) == (0, 1)
    assert count >= 4
    dimensions = set()
    for index in range(count):
        width, height, _palette, reserved_byte, _planes, _depth, size, offset = (
            struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
        )
        assert reserved_byte == 0
        assert offset >= 6 + count * 16
        assert size > 0
        assert offset + size <= len(data)
        dimensions.add((width or 256, height or 256))
    assert (16, 16) in dimensions
    assert (256, 256) in dimensions


def test_separate_app_state(monkeypatch, tmp_path):
    monkeypatch.delenv("STRAPMAN_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("STRAPMAN_EDITION", LITE)
    lite = app_directory()
    monkeypatch.setenv("STRAPMAN_EDITION", BOOTLEGGER)
    pro = app_directory()
    assert lite != pro
    assert pro == lite / "bootlegger"
    assert DEFAULT_SETTINGS["theme_mode"] == "Purple Night"
