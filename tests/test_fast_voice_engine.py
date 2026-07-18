from app.services.fast_voice_engine import FastVoiceEngine


def test_parse_digits_accepts_spaced_numeric_output():
    assert FastVoiceEngine._parse_digits("1 2 3 4 5 6") == "123456"


def test_parse_digits_accepts_mixed_words_and_numbers():
    assert FastVoiceEngine._parse_digits("one 2 तीन four 5 six") == "123456"


def test_parse_digits_accepts_devanagari_numbers():
    assert FastVoiceEngine._parse_digits("१ २ ३ ४ ५ ६") == "123456"


def test_parse_digits_ignores_unknown_tokens_without_losing_known_digits():
    assert FastVoiceEngine._parse_digits("please one unknown 2 बोलो three") == "123"
