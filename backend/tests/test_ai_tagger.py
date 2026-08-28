import pytest
from app.services.ai_tagger import AITagResult, detect_known_studio

def test_detect_known_studio():
    assert detect_known_studio("Sanix_Iron_Man.stl", "") == "Sanix"
    assert detect_known_studio("batman_stl", "Gambody 3D printing STL model") == "Gambody"
    assert detect_known_studio("Wicked_SpiderMan.rar", "") == "Wicked"
    assert detect_known_studio("random_cube.stl", "just a cube") is None

def test_ai_tag_result_studio():
    res = AITagResult(predicted_name="Batman", studio="Sanix", category="Figurine", print_type="Resin")
    assert res.studio == "Sanix"
    assert res.predicted_name == "Batman"
