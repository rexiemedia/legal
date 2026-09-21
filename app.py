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


def _safe_text(value: str | None, default: str, maximum: int) -> str:
    """
    Accept normal URL query text while preventing excessively large values.

    Jinja autoescaping provides the HTML-context protection when these values
    are rendered into templates.
    """
    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    if len(value) > maximum:
        return default

    return value


# Strictly accept #rgb or #rrggbb.
HEX_COLOR_RE = re.compile(
    r"^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$"
)


DEFAULT_THEME = {
    "bg": "#f5f6f8",
    "card": "#ffffff",
    "text": "#0d1b2a",
    "muted": "#516072",
    "accent": "#0a4fc4",
    "border": "#d9dfe7",
}


def _safe_color(value: str | None, default: str) -> str:
    """
    Only permit #rgb or #rrggbb.

    Values such as:
        red
        rgb(...)
        url(...)
        javascript:...
        #fff; color:red
        </style><script>...
    are rejected.
    """
    if value is None:
        return default

    value = value.strip()

    if HEX_COLOR_RE.fullmatch(value):
        return value

    return default


def get_request_theme() -> dict[str, str]:
    """
    Read theme colors from the query string and strictly validate them.
    """

    return {
        key: _safe_color(
            request.args.get(key),
            DEFAULT_THEME[key],
        )
        for key in DEFAULT_THEME
    }

def get_request_site() -> dict:
    """
    Allow product, app, and company to be customized per URL.

    Values are still rendered through Jinja autoescaping.
    Email remains server-controlled.
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

    theme = get_request_theme()

    css = f"""/* ROO Secure dynamic legal-page theme */
:root {{
  --bg: {theme["bg"]};
  --surface: {theme["card"]};
  --ink: {theme["text"]};
  --muted: {theme["muted"]};
  --rule: {theme["border"]};
  --accent: {theme["accent"]};
}}
"""

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