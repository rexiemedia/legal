"""
Security and behavior test suite for the ROO Secure legal-pages service.

Run with:
    pip install pytest --break-system-packages
    pytest -v

These tests do not hit a live server — they use Flask's test client directly
against app.py, so they run the same in CI, locally, or before a Railway
deploy.
"""
import sys
import os
import re
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app, _hits


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    _hits.clear()
    return app.test_client()


def product_field(html):
    m = re.search(r"<dt>Product</dt><dd>(.*?)</dd>", html)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Routes respond
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/privacy", "/terms", "/security"])
def test_pages_load(client, path):
    r = client.get(path)
    assert r.status_code == 200


def test_index_redirects_to_privacy(client):
    r = client.get("/")
    assert r.status_code in (301, 302)
    assert r.headers["Location"].startswith("/privacy")


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_unknown_route_returns_404_page(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# XSS / injection: text fields (product, app, company)
# ---------------------------------------------------------------------------

ATTACK_TEXT_PAYLOADS = [
    # --- Classic tag/event-handler XSS ---
    "<script>alert(1)</script>",
    "<ScRiPt>alert(1)</ScRiPt>",              # mixed case
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "<body onload=alert(1)>",
    "<iframe src=javascript:alert(1)>",
    "<a href=javascript:alert(1)>x</a>",
    "<input autofocus onfocus=alert(1)>",
    "<details open ontoggle=alert(1)>",

    # --- Dangerous URL schemes ---
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",                    # case-insensitive check
    "vbscript:msgbox(1)",
    "data:text/html,<script>alert(1)</script>",

    # --- Raw JS execution constructs ---
    "eval(alert(1))",
    "Function('alert(1)')()",
    "setTimeout('alert(1)',0)",
    "new Function('alert(1)')",

    # --- Server-side template injection (SSTI) probes ---
    "{{7*7}}",             # Jinja
    "{{config}}",          # Jinja — attempted config disclosure
    "${7*7}",              # various EL/JS-template style
    "#{7*7}",              # Ruby/Slim style
    "<%= 7*7 %>",          # ERB style

    # --- Attribute / quote breakout ---
    '" onmouseover=alert(1) x="',
    "' onmouseover=alert(1) x='",
    "`alert(1)`",

    # --- Encoding tricks (arrive pre-decoded by Werkzeug before validation) ---
    "%3Cscript%3Ealert(1)%3C/script%3E",           # URL-encoded
    "&#60;script&#62;alert(1)&#60;/script&#62;",   # HTML entity encoded
    "\\x3cscript\\x3e",                             # backslash-escaped hex

    # --- Case / whitespace / null-byte bypass attempts ---
    "SCRIPT",                                  # bare keyword, uppercase
    "EVAL(1)",
    "Eval (alert(1))",                         # space inserted before paren
    "java\tscript:alert(1)",                   # tab inserted mid-keyword
    "on\x00error=alert(1)",                    # embedded null byte

    # --- Header / log injection via CRLF ---
    "product\r\nSet-Cookie: pwned=1",
    "product%0d%0aSet-Cookie:%20pwned=1",

    # --- Path traversal syntax ---
    "..\\..\\windows\\win.ini",

    # --- SQL / command injection shaped strings (not applicable to this app,
    #     but worth confirming they're inert here too — defense in depth) ---
    "' OR '1'='1",
    "1; DROP TABLE users--",
    "; rm -rf /",
    "$(whoami)",
    "`whoami`",

    # --- Unicode homoglyph attempt (Cyrillic 'і' U+0456 in place of Latin 'i') ---
    "<scr\u0456pt>alert(1)</scr\u0456pt>",

    # --- Prototype-pollution-shaped strings ---
    "__proto__[x]=1",
    "constructor.prototype.x=1",
]


@pytest.mark.parametrize("payload", ATTACK_TEXT_PAYLOADS)
def test_attack_payloads_in_product_fall_back_to_default(client, payload):
    r = client.get("/security", query_string={"product": payload})
    html = r.get_data(as_text=True)
    assert product_field(html) == "ROO Secure"
    # Also confirm the raw payload never appears unescaped anywhere in the page.
    assert payload not in html or payload.lower() in ("script", "eval(1)")


def test_path_traversal_syntax_is_accepted_but_inert(client):
    # '.' and '/' are both in the allowlist (needed for names like
    # "Acme, Inc." and "roosecure.com"), and path-traversal syntax matches
    # no blocklist keyword, so this value is NOT rejected — unlike every
    # payload above. This is documented on purpose, not an oversight: the
    # product field is only ever displayed as text and is never used to
    # open a file or build a path anywhere in this app, so it's harmless
    # here. If `product` (or any allowlisted text field) is ever used to
    # construct a filesystem path in the future, this test should start
    # failing and that usage should be re-reviewed before shipping.
    payload = "../../etc/passwd"
    r = client.get("/security", query_string={"product": payload})
    html = r.get_data(as_text=True)
    assert product_field(html) == payload


LEGIT_NAMES = [
    "AgentLab",
    "ROO Mobile",
    "Acme, Inc.",
    "O'Brien & Sons",
    "Product-Name_2 (Beta)",
]


@pytest.mark.parametrize("name", LEGIT_NAMES)
def test_legitimate_product_names_pass_through(client, name):
    r = client.get("/security", query_string={"product": name})
    html = r.get_data(as_text=True)
    field = product_field(html)
    assert field is not None
    # HTML-escaped equivalents are fine (e.g. ' -> &#39;)
    assert field.replace("&#39;", "'").replace("&amp;", "&") == name


def test_malformed_query_string_is_inert(client):
    # A stray '?' (no '&') is just literal text in the product value, not a
    # second parameter. This was reported as "XSS" but is standard query
    # string parsing behavior — this test locks in that understanding.
    r = client.get("/security?product=AgentL?email=attacker@evil.com")
    html = r.get_data(as_text=True)
    assert "support@roosecure.com" in html          # real email untouched
    assert "attacker@evil.com" not in html.split("Product")[0]


# ---------------------------------------------------------------------------
# Email cannot be overridden via URL
# ---------------------------------------------------------------------------

def test_email_override_rejected_when_domain_not_allowlisted(client):
    r = client.get("/privacy", query_string={"email": "attacker@evil.com"})
    html = r.get_data(as_text=True)
    assert "attacker@evil.com" not in html
    assert "support@roosecure.com" in html


def test_email_override_rejected_for_personal_addresses(client):
    # Same-shaped request as the real one reported during testing: a
    # personal gmail.com address is not on the allowlist, so it must not
    # appear on the page even though it's a syntactically valid email.
    r = client.get("/terms", query_string={"email": "oldwarri1@gmail.com"})
    html = r.get_data(as_text=True)
    assert "oldwarri1@gmail.com" not in html
    assert "support@roosecure.com" in html


def test_email_override_accepted_when_domain_allowlisted(client):
    r = client.get(
        "/privacy", query_string={"email": "custom-team@roosecure.com"}
    )
    html = r.get_data(as_text=True)
    assert "custom-team@roosecure.com" in html


def test_malformed_email_override_rejected(client):
    r = client.get(
        "/privacy",
        query_string={"email": "not-an-email\r\nSet-Cookie: pwned=1"},
    )
    html = r.get_data(as_text=True)
    assert "Set-Cookie" not in html
    assert "support@roosecure.com" in html


# ---------------------------------------------------------------------------
# Theme colors: strict hex allowlist
# ---------------------------------------------------------------------------

def test_valid_hex_color_applied(client):
    r = client.get("/style.css", query_string={"accent": "#ff6b6b"})
    css = r.get_data(as_text=True)
    assert "--accent: #ff6b6b;" in css


def test_no_query_params_emits_no_override(client):
    # Dark-mode regression guard: with no theme params, this endpoint must
    # emit nothing that would win the cascade over style.css's own
    # @media (prefers-color-scheme: dark) rules.
    r = client.get("/style.css")
    css = r.get_data(as_text=True)
    assert ":root" not in css


BAD_COLOR_PAYLOADS = [
    "red",
    "rgb(0,0,0)",
    "url(evil.com)",
    "javascript:alert(1)",
    "#fff}*{display:none}",
    "#ff6b6b;background-image:url(evil.com)",
    "#fff; color:red",
    "</style><script>alert(1)</script>",
]


@pytest.mark.parametrize("payload", BAD_COLOR_PAYLOADS)
def test_invalid_colors_rejected(client, payload):
    r = client.get("/style.css", query_string={"accent": payload})
    css = r.get_data(as_text=True)
    assert payload not in css
    # Invalid input is dropped, not swapped for a hardcoded default — an
    # invalid accent must not force any color, light or dark, via this
    # endpoint (see test_no_query_params_emits_no_override above).
    assert ":root" not in css


def test_partial_override_only_sets_that_variable(client):
    r = client.get("/style.css", query_string={"accent": "#ff6b6b"})
    css = r.get_data(as_text=True)
    assert "--accent: #ff6b6b;" in css
    assert "--bg" not in css
    assert "--surface" not in css


# ---------------------------------------------------------------------------
# Path traversal / methods
# ---------------------------------------------------------------------------

def test_static_path_traversal_blocked(client):
    r = client.get("/static/../app.py")
    assert r.status_code != 200


def test_trace_method_not_allowed(client):
    r = client.open("/privacy", method="TRACE")
    assert r.status_code in (405, 501)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def test_security_headers_present(client):
    r = client.get("/privacy")
    h = r.headers
    assert "Content-Security-Policy" in h
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Werkzeug" not in h.get("Server", "")


def test_hsts_only_set_when_request_is_secure(client):
    r = client.get("/privacy")  # test client requests are not "secure"
    assert "Strict-Transport-Security" not in r.headers


def test_http_forwarded_proto_redirects_to_https(client):
    r = client.get("/privacy", headers={"X-Forwarded-Proto": "http"})
    assert r.status_code == 301
    assert r.headers["Location"].startswith("https://")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_triggers_after_120_requests(client):
    for _ in range(120):
        client.get("/security")
    r = client.get("/security")
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_rate_limit_is_per_route_bucket_shared_by_ip(client):
    # NOTE: /style.css shares the same rate_limit decorator and IP bucket as
    # the page routes. A single page load costs 2 hits (page + theme_css),
    # so a browser effectively gets ~60 page loads/hour, not 120. Flagging
    # this as a known behavior, not asserting a fix, in case that's not
    # what you want in production.
    for _ in range(60):
        client.get("/security")
        client.get("/style.css")
    r = client.get("/security")
    assert r.status_code == 429