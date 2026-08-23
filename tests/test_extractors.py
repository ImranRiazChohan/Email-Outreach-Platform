from services.email_extractor import extract_emails_from_html, select_primary_email
from services.phone_extractor import extract_phones_from_html, select_primary_phone


def test_extract_emails_from_mailto_and_text():
    html = """
    <html><body>
      <a href="mailto:info@business.com">Email us</a>
      <p>Or reach sales@business.com for quotes.</p>
      <p>Invalid: not-an-email</p>
    </body></html>
    """
    emails = extract_emails_from_html(html)
    assert "info@business.com" in emails
    assert "sales@business.com" in emails
    assert "not-an-email" not in emails


def test_select_primary_email_prioritizes_business_prefixes():
    emails = {"webmaster@business.com", "hello@business.com", "random@business.com"}
    assert select_primary_email(emails) == "hello@business.com"


def test_select_primary_email_empty_returns_none():
    assert select_primary_email(set()) is None


def test_extract_emails_from_anywhere_on_the_page():
    html = """
    <html><body>
      <header><p>random@header.com</p></header>
      <p>Body text mentioning body@company.com in the main content.</p>
      <footer>
        <a href="mailto:info@company.com">Email us</a>
      </footer>
    </body></html>
    """
    emails = extract_emails_from_html(html)
    assert emails == {"random@header.com", "body@company.com", "info@company.com"}


def test_extract_phones_from_tel_link_and_text():
    html = """
    <html><body>
      <a href="tel:+923001234567">Call us</a>
      <p>Landline: (021) 111-222-333</p>
    </body></html>
    """
    phones = extract_phones_from_html(html)
    assert any("923001234567" in p or "+923001234567" == p for p in phones)


def test_select_primary_phone_prefers_plus_prefixed():
    phones = {"03001234567", "+923001234567"}
    assert select_primary_phone(phones) == "+923001234567"


def test_select_primary_phone_empty_returns_none():
    assert select_primary_phone(set()) is None
