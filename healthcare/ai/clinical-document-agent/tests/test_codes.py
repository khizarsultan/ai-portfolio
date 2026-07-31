from src.codes import code_lookup


def test_known_codes_valid():
    assert code_lookup.is_valid("N39.0")
    assert code_lookup.is_valid("99213")
    assert code_lookup.system_of("N39.0") == "ICD-10"
    assert code_lookup.system_of("99213") == "CPT"


def test_invented_code_invalid():
    assert not code_lookup.is_valid("M54.99")
    assert code_lookup.system_of("ZZZ") == "?"


def test_display_lookup():
    assert "diabetes" in code_lookup.display("E11.65").lower()
