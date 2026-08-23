from utils.phone_utils import normalize_phone
from utils.url_utils import normalize_domain, normalize_url


def test_normalize_domain_strips_scheme_and_www():
    assert normalize_domain("https://www.example.com/") == "example.com"
    assert normalize_domain("http://example.com") == "example.com"
    assert normalize_domain("www.example.com") == "example.com"
    assert normalize_domain("example.com/some/path") == "example.com"


def test_normalize_domain_handles_none_and_blank():
    assert normalize_domain(None) is None
    assert normalize_domain("") is None
    assert normalize_domain("   ") is None


def test_normalize_url_adds_scheme_and_strips_trailing_slash():
    assert normalize_url("example.com/") == "https://example.com"
    assert normalize_url("https://example.com/path/") == "https://example.com/path"


def test_normalize_phone_matches_across_formats():
    variants = ["+92 300 1234567", "0300-1234567", "92 300 1234567"]
    normalized = {normalize_phone(v, country="Pakistan") for v in variants}
    assert len(normalized) == 1
    assert None not in normalized


def test_normalize_phone_handles_missing_input():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
