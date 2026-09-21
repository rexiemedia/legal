from flask import Flask, render_template, request, make_response, redirect, url_for
from datetime import date, datetime, timedelta
from functools import wraps
import time
from collections import defaultdict

app = Flask(__name__)

# ---------- Defaults ----------
DEFAULTS = {
    "product": "ROO Secure",
    "app": "roosecure.com",
    "company": "ROO Secure IT Solutions",
    "email": "legal@roosecure.com",
    "version": "2026.09",
    "effective": date.today().isoformat(),
}

DEFAULT_THEME = {
    "bg": "#0f1115",
    "card": "#161b22",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#58a6ff",
    "border": "#30363d",
}

# ---------- Simple in-memory rate limiter ----------
request_log = defaultdict(list)
RATE_LIMIT_WINDOW = 86400   # 1 day
RATE_LIMIT_MAX = 120

def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip:
            ip = ip.split(",")[0].strip()
        now = time.time()
        request_log[ip] = [t for t in request_log[ip] if now - t < RATE_LIMIT_WINDOW]
        if len(request_log[ip]) >= RATE_LIMIT_MAX:
            resp = make_response("Rate limit exceeded. Try again tomorrow.", 429)
            resp.headers["Retry-After"] = str(RATE_LIMIT_WINDOW)
            return resp
        request_log[ip].append(now)
        return f(*args, **kwargs)
    return decorated

# ---------- Helpers ----------
def get_context():
    ctx = DEFAULTS.copy()
    for key in DEFAULTS:
        if value := request.args.get(key):
            ctx[key] = value

    theme = DEFAULT_THEME.copy()
    for key in DEFAULT_THEME:
        if value := request.args.get(key):
            if value.startswith("#") and len(value) in (4, 7):
                theme[key] = value
    ctx["theme"] = theme
    return ctx

def cached(template):
    ctx = get_context()
    resp = make_response(render_template(template, **ctx))
    resp.headers["Cache-Control"] = "public, max-age=86400, s-maxage=86400"
    return resp

# ---------- Routes ----------
@app.route("/")
def index():
    return redirect(url_for("privacy"))

@app.route("/privacy")
@rate_limit
def privacy():
    return cached("privacy.html")

@app.route("/terms")
@rate_limit
def terms():
    return cached("terms.html")

@app.route("/security")
@rate_limit
def security():
    return cached("security.html")

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)