from services.website_analyzer import (
    analyze_website_html,
    calculate_website_quality_score,
    detect_chatbot,
)

GOOD_HTML = """
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/style.css">
  <link rel="icon" href="/favicon.ico">
</head>
<body>
  <header><nav><a href="/">Home</a><a href="/about">About</a><a href="/contact">Contact</a></nav></header>
  <main>
    <section>
      <h1>Welcome</h1>
      <p>Call us or book an appointment today!</p>
      <button class="btn">Book Now</button>
      <form>
        <input type="email" name="email">
        <textarea name="message"></textarea>
      </form>
    </section>
  </main>
  <footer>Contact: info@business.com</footer>
</body>
</html>
"""

POOR_HTML = """
<html><body><p>We are a business. Call us.</p></body></html>
"""

CHATBOT_HTML = """
<html><body>
<script src="https://widget.intercom.io/widget/abc123"></script>
</body></html>
"""


def test_detect_chatbot_positive():
    assert detect_chatbot(CHATBOT_HTML) is True


def test_detect_chatbot_negative():
    assert detect_chatbot(GOOD_HTML) is False


def test_analyze_website_html_good_site_scores_high():
    analysis_data, quality_score = analyze_website_html(
        GOOD_HTML,
        https_enabled=True,
        email_detected=True,
        phone_detected=True,
        fetch_seconds=0.5,
        page_size_bytes=50_000,
    )
    assert analysis_data["mobile_friendly"] is True
    assert analysis_data["contact_form_detected"] is True
    assert analysis_data["call_to_action_detected"] is True
    assert analysis_data["navigation_detected"] is True
    assert analysis_data["chatbot_detected"] is False
    assert quality_score >= 80


def test_analyze_website_html_poor_site_scores_low():
    analysis_data, quality_score = analyze_website_html(
        POOR_HTML,
        https_enabled=False,
        email_detected=False,
        phone_detected=False,
        fetch_seconds=6.0,
        page_size_bytes=4_000_000,
    )
    assert analysis_data["mobile_friendly"] is False
    assert analysis_data["contact_form_detected"] is False
    assert quality_score <= 30


def test_calculate_website_quality_score_bounds():
    perfect = {
        "https_enabled": True,
        "mobile_friendly": True,
        "navigation_detected": True,
        "call_to_action_detected": True,
        "phone_number_detected": True,
        "contact_form_detected": True,
        "good_page_structure": True,
        "modern_design_score": 100,
        "performance_score": 100,
    }
    assert calculate_website_quality_score(perfect) == 100

    empty = {
        "https_enabled": False,
        "mobile_friendly": False,
        "navigation_detected": False,
        "call_to_action_detected": False,
        "phone_number_detected": False,
        "contact_form_detected": False,
        "good_page_structure": False,
        "modern_design_score": 0,
        "performance_score": 0,
    }
    assert calculate_website_quality_score(empty) == 0
