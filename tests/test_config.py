"""Settings persistence tests. ARMYLIGHT_HOME points config + logs at a tmp dir
so these never touch the real ~/Library."""


import pytest

from army_light import config


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ARMYLIGHT_HOME", str(tmp_path))
    yield tmp_path


def test_defaults_match_verified_protocol():
    # Verified on a real BTS ARMY Bomb Ver. 4 ("BTS_V4 LS"), 2026-06-03.
    s = config.Settings()
    assert s.wand_name_match == "BTS"
    assert s.service_uuid == "0001fe01-0000-1000-8000-00805f9800c4"
    assert s.color_char_uuid == "0001ff01-0000-1000-8000-00805f9800c4"
    assert s.commit_char_uuid == "0001ff13-0000-1000-8000-00805f9800c4"
    assert s.packet_format == "bts_v4"
    # ff01 is (read,write) — with-response ONLY. CoreBluetooth silently drops
    # no-response writes to it (no error, no color change), so the default
    # must be with-response. Verified both ways on a real V4 unit.
    assert s.write_with_response is True
    # V4 needs no white wake packet (it would flash white before every color).
    assert s.wake_on_connect is False


def test_load_creates_default_file(isolated_home):
    assert not config.config_path().exists()
    s = config.Settings.load()
    assert config.config_path().exists()
    assert s.packet_format == "bts_v4"


def test_save_load_round_trip():
    s = config.Settings.load()
    s.packet_format = "triones"
    s.wand_address = "ABC-123"
    s.save()
    again = config.Settings.load()
    assert again.packet_format == "triones"
    assert again.wand_address == "ABC-123"


def test_load_ignores_unknown_keys(isolated_home):
    config.config_path().write_text('{"packet_format": "raw_rgb", "future_field": 42}')
    s = config.Settings.load()
    assert s.packet_format == "raw_rgb"
    assert not hasattr(s, "future_field")


def test_load_tolerates_corrupt_file(isolated_home):
    config.config_path().write_text("{ not json")
    s = config.Settings.load()  # falls back to defaults, doesn't raise
    assert s.packet_format == "bts_v4"


def test_logs_dir_under_home(isolated_home):
    assert str(config.log_path()).startswith(str(isolated_home))
