from app.config import Zone
from app.locate import describe, grid_position


def test_gemini_phrase_is_used(settings):
    assert describe((0.4, 0.4, 0.5, 0.5), settings, phrase="on the desk next to the laptop") == \
        ("ai", "on the desk next to the laptop")


def test_no_phrase_uses_camera_view(settings):
    assert describe((0.05, 0.05, 0.10, 0.10), settings)[1] == "in the top-left of the camera view"
    assert grid_position((0.45, 0.40, 0.55, 0.50))[1] == "in the centre of the camera view"
    assert grid_position((0.80, 0.40, 0.90, 0.50))[1] == "in the right side of the camera view"


def test_saved_zones_win_then_gemini(settings):
    drawer = [Zone("drawer", "in the drawer", [(0, 0), (0.3, 0), (0.3, 0.3), (0, 0.3)])]
    assert describe((0.1, 0.1, 0.15, 0.15), settings, phrase="on the table", saved_zones=drawer) == \
        ("drawer", "in the drawer")
    assert describe((0.6, 0.6, 0.65, 0.65), settings, phrase="on the table", saved_zones=drawer) == \
        ("ai", "on the table")


def test_zones_mode_uses_only_zones(settings):
    settings.location_mode = "zones"
    assert describe((0.1, 0.7, 0.2, 0.8), settings, phrase="on the table") == ("desk", "on the desk")
