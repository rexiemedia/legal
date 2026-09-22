import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from functools import wraps

from flask import Flask, Response, make_response, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600


# ---------------------------------------------------------------------------
# Proxy configuration
# ---------------------------------------------------------------------------

# Railway terminates TLS at its edge and forwards X-Forwarded-* headers.
# Railway only: 1
# Cloudflare -> Railway: 2
PROXY_HOPS = int(os.environ.get("PROXY_HOPS", "1"))

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=PROXY_HOPS,
    x_proto=PROXY_HOPS,
    x_host=PROXY_HOPS,
)


# ---------------------------------------------------------------------------
# Site details
# ---------------------------------------------------------------------------

def _display_date(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day} {d:%B %Y}"
    except ValueError:
        return iso


_effective = os.environ.get(
    "LEGAL_EFFECTIVE_DATE",
    "2026-09-21",
)

SITE = {
    # These are the server-controlled defaults.
    "product": os.environ.get("SITE_PRODUCT", "ROO Secure"),
    "app": os.environ.get("SITE_APP", "roosecure.com"),
    "company": os.environ.get(
        "SITE_COMPANY",
        "ROO Secure IT Solutions",
    ),
    "email": os.environ.get(
        "SITE_EMAIL",
        "support@roosecure.com",
    ),
    "version": os.environ.get(
        "LEGAL_VERSION",
        "2026.09",
    ),
    "effective": _effective,
    "effective_display": _display_date(_effective),
    "year": _effective[:4],
}


# ---------------------------------------------------------------------------
# Dynamic URL values
# ---------------------------------------------------------------------------

# Only allow simple printable text for product/app.
# These values are still rendered through Jinja autoescaping.
MAX_PRODUCT_LENGTH = 120
MAX_APP_LENGTH = 120

# Allowlist: letters, numbers, spaces, and a small set of punctuation normal
# product/company/app names actually use. Anything outside this — <, >, {, },
# ;, backticks, quotes, "javascript:", "eval(", "onerror=", etc. — is rejected
# outright rather than escaped-and-shown. This is defense in depth, not a fix
# for an exploit: Jinja autoescaping already prevents execution. The point is
# that a cybersecurity company's own pages shouldn't reflect attack-looking
# strings back to the visitor at all, even harmlessly.
SAFE_TEXT_RE = re.compile(r"^[A-Za-z0-9 .,&'()/_-]+$")

# Some attack-shaped strings ("eval(...)", "script") pass the character
# allowlist above but are still worth rejecting outright rather than
# displaying back, even harmlessly, on a security company's own pages.
DANGEROUS_SUBSTRINGS = (
    "script", "eval(", "javascript:", "vbscript:", "onerror",
    "onload", "onclick", "onmouseover", "expression(", "alert(",
)


def _safe_text(value: str | None, default: str, maximum: int) -> str:
    """
    Accept only names built from the allowlisted character set above, and
    without attack-shaped keywords. Anything else (length violation,
    disallowed characters, blocklisted keyword, empty) falls back to the
    default rather than being sanitized or echoed.
    """
    if value is None:
        return default

    value = value.strip()

    if not value or len(value) > maximum:
        return default

    if not SAFE_TEXT_RE.fullmatch(value):
        return default

    lowered = value.lower()
    if any(bad in lowered for bad in DANGEROUS_SUBSTRINGS):
        return default

    return value


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,190}\.[A-Za-z]{2,24}$")

# Which domains are allowed to be used via ?email=. Anything outside this
# list falls back to SITE_EMAIL, no exceptions. Unrestricted email override
# would let anyone build a link on this domain that points a visitor at an
# attacker's inbox — a phishing setup, and a bad one for a cybersecurity
# company's own legal pages to enable. Set as a comma-separated list in
# Railway, e.g. "roosecure.com,roomobile.app".
ALLOWED_EMAIL_DOMAINS = {
    d.strip().lower()
    for d in os.environ.get("ALLOWED_EMAIL_DOMAINS", "roosecure.com").split(",")
    if d.strip()
}


def _safe_email(value: str | None, default: str) -> str:
    if value is None:
        return default

    value = value.strip()

    if not EMAIL_RE.fullmatch(value):
        return default

    domain = value.rsplit("@", 1)[1].lower()
    if domain not in ALLOWED_EMAIL_DOMAINS:
        return default

    return value


# Strictly accept #rgb or #rrggbb.
HEX_COLOR_RE = re.compile(
    r"^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$"
)


def get_request_theme() -> dict[str, str]:
    """
    Read theme colors from the query string, strictly validated, but only
    include a key when the caller actually passed a valid override.

    This matters for dark mode: static/style.css defines light values on
    :root and dark values under @media (prefers-color-scheme: dark). This
    stylesheet loads after that one, so if it always emitted every variable
    (even defaults), it would permanently win the cascade and silently kill
    dark mode for every visitor who didn't pass theme colors in the URL.
    Only overridden colors are emitted here; everything else is left for
    style.css's own light/dark rules to decide.
    """

    overrides = {}
    for key, css_var in THEME_CSS_VARS.items():
        value = _safe_color_override(request.args.get(key))
        if value is not None:
            overrides[css_var] = value
    return overrides


THEME_CSS_VARS = {
    "bg": "--bg",
    "card": "--surface",
    "text": "--ink",
    "muted": "--muted",
    "border": "--rule",
    "accent": "--accent",
}


def _safe_color_override(value: str | None) -> str | None:
    """Like _safe_color, but returns None (not a default) when absent/invalid."""
    if value is None:
        return None
    value = value.strip()
    return value if HEX_COLOR_RE.fullmatch(value) else None

def get_request_site() -> dict:
    """
    Allow product, app, company, and email to be customized per URL.

    Text fields are still rendered through Jinja autoescaping. Email is
    additionally restricted to a domain allowlist (see ALLOWED_EMAIL_DOMAINS)
    — an arbitrary email address can never be set on this domain's pages,
    only ones on a pre-approved domain.
    """

    site = dict(SITE)

    site["product"] = _safe_text(
        request.args.get("product"),
        SITE["product"],
        MAX_PRODUCT_LENGTH,
    )

    site["app"] = _safe_text(
        request.args.get("app"),
        SITE["app"],
        MAX_APP_LENGTH,
    )

    site["company"] = _safe_text(
        request.args.get("company"),
        SITE["company"],
        160,
    )

    site["email"] = _safe_email(
        request.args.get("email"),
        SITE["email"],
    )

    return site

@app.context_processor
def inject_site():
    return get_request_site()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_WINDOW = 3600  # 1 hour
RATE_MAX = 120       # 120 requests per IP per hour

_hits = defaultdict(deque)


def rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = time.time()

        # Keep memory bounded.
        if len(_hits) > 5000:
            for key in [
                key
                for key, queue in _hits.items()
                if not queue or now - queue[-1] > RATE_WINDOW
            ]:
                del _hits[key]

        queue = _hits[ip]

        while queue and now - queue[0] > RATE_WINDOW:
            queue.popleft()

        if len(queue) >= RATE_MAX:
            resp = make_response(
                "Too many requests. Please try again later.",
                429,
            )
            resp.headers["Retry-After"] = str(RATE_WINDOW)
            return resp

        queue.append(now)

        return f(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

@app.before_request
def force_https():
    # Only acts behind a proxy that says the original request was plain HTTP.
    if (
        request.headers.get("X-Forwarded-Proto") == "http"
        and request.path != "/health"
    ):
        return redirect(
            request.url.replace("http://", "https://", 1),
            code=301,
        )


@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    )

    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    resp.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    if request.is_secure:
        resp.headers["Strict-Transport-Security"] = (
            "max-age=31536000"
        )

    return resp


# ---------------------------------------------------------------------------
# Dynamic theme stylesheet
# ---------------------------------------------------------------------------

@app.route("/style.css")
@rate_limit
def theme_css():
    """
    Generates a same-origin stylesheet containing only validated colors.

    Because this is an external same-origin stylesheet, it remains compatible
    with:

        style-src 'self'

    in the CSP above.
    """

    overrides = get_request_theme()

    if overrides:
        decls = "\n".join(f"  {var}: {val};" for var, val in overrides.items())
        css = f"/* ROO Secure dynamic legal-page theme override */\n:root {{\n{decls}\n}}\n"
    else:
        # No valid overrides in the URL — emit nothing so style.css's own
        # light/dark :root rules apply untouched.
        css = "/* No theme override — using site defaults (light/dark auto) */\n"

    response = Response(
        css,
        mimetype="text/css",
    )

    # Theme depends on the query string.
    response.headers["Cache-Control"] = (
        "public, max-age=3600"
    )

    return response


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

def page(template):
    response = make_response(
        render_template(template)
    )

    response.headers["Cache-Control"] = (
        "public, max-age=3600"
    )

    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("privacy"))


@app.route("/privacy")
@rate_limit
def privacy():
    return page("privacy.html")


@app.route("/terms")
@rate_limit
def terms():
    return page("terms.html")


@app.route("/security")
@rate_limit
def security():
    return page("security.html")


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
    )