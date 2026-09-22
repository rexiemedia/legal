# Railway Deployment Guide – ROO Secure Legal Service

This guide walks you through deploying the legal pages service (Privacy, Terms, Security) to Railway from a private GitHub repository.

---

## 1. Prerequisites

- A Railway account → [https://railway.app](https://railway.app)
- A private GitHub repository containing this project
- Domain (optional but recommended): `legal.roosecure.com`

---

## 2. Project Structure

```text
legal-service/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml          # local testing only
├── static/
│   ├── style.css
│   └── toc.js
├── templates/
│   ├── base.html
│   ├── privacy.html
│   ├── terms.html
│   ├── security.html
│   └── 404.html
├── tests/
│   └── test_app.py             # run before every deploy — see §13
└── read-railway-deploy.md      # this file
```

---

## 3. Push to Private GitHub Repo

```bash
cd legal-service
git init
git add .
git commit -m "Initial legal service"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/roosecure-legal.git
git push -u origin main
```

Make sure the repository is set to **Private**.

---

## 4. Deploy on Railway

### Step-by-step

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project**
3. Choose **Deploy from GitHub repo**
4. Select your private repository (`roosecure-legal`)
5. Railway will automatically detect the `Dockerfile`
6. Click **Deploy**

Railway will build the multi-stage Docker image and start the service on the port it injects via `$PORT`.

---

## 5. Configure the Service

### Environment variables

Unlike the original version, the site's identity (name, company, contact email, dates) is **not** read from the URL — it's server-controlled via Railway's Variables tab. This closes the hole where anyone could craft a link showing a different company name or, worse, a different contact email on your own legal pages.

| Variable              | Purpose                                 | Default (if unset)              |
|------------------------|------------------------------------------|----------------------------------|
| `PORT`                 | Railway sets this automatically          | `8080`                           |
| `PROXY_HOPS`           | Number of reverse proxies in front of the app — `1` for Railway alone, `2` if you also put Cloudflare's proxy in front | `1` |
| `SITE_PRODUCT`         | Default product name                     | `ROO Secure`                     |
| `SITE_APP`             | Default app identifier                   | `roosecure.com`                  |
| `SITE_COMPANY`         | Legal entity name                        | `ROO Secure IT Solutions`        |
| `SITE_EMAIL`           | Contact email — **cannot be overridden by URL, on purpose** | `support@roosecure.com` |
| `LEGAL_VERSION`        | Policy version string                    | `2026.09`                        |
| `LEGAL_EFFECTIVE_DATE` | Effective date, `YYYY-MM-DD`             | `2026-09-21`                     |

Set these once in Railway; you should not need to touch `app.py` again to rebrand the pages for your own site.

### Custom Domain

1. Open your service on Railway
2. Go to **Settings → Domains**
3. Click **Custom Domain**
4. Add: `legal.roosecure.com`
5. Create the CNAME record (and any TXT verification record) that Railway shows you at your DNS provider
6. If your registrar sits behind Cloudflare, set the DNS record to **DNS only** (grey cloud) until Railway's certificate shows as issued — Cloudflare's proxy can block the Let's Encrypt validation challenge. Switch it to proxied afterward if you want.
7. If you use an apex domain (`roosecure.com` with no subdomain) and see the certificate stuck on "Validating Challenges," check that your DNS host supports CNAME flattening/ALIAS records, and that you have no CAA record blocking `letsencrypt.org`.

Certificate issuance is automatic (Railway uses Let's Encrypt) and usually completes within an hour, but can take up to 72 hours.

After DNS propagates you will have:

```
https://legal.roosecure.com/privacy
https://legal.roosecure.com/terms
https://legal.roosecure.com/security
```

---

## 6. Linking from Other Apps

### Main website (OCI)

```html
<a href="https://legal.roosecure.com/privacy">Privacy Policy</a>
<a href="https://legal.roosecure.com/terms">Terms of Use</a>
<a href="https://legal.roosecure.com/security">Security</a>
```

### Other web / mobile apps (dynamic)

The `product`, `app`, and `company` fields, and the theme colors, can be customized per link so each of your own products can point at these shared legal pages with their own name and brand colors:

```
https://legal.roosecure.com/privacy?product=ROO%20Mobile&app=ios
https://legal.roosecure.com/terms?product=ClientPortal&company=ROO%20Secure%20IT%20Solutions
https://legal.roosecure.com/security?product=AgentLab&accent=%23ff6b6b
http://192.168.1.10:8080/terms?product=Amex&email=oldwarri1@gmail.com&accent=%23ff6b6b
http://192.168.1.10:8080/terms?product=AmexCard&company=EQ%20Attendnace&email=oldwarri1@gmail.com&accent=%23ff6b6b
```

**Important:** query parameters must be joined with `&`, not `?`. `?product=A?email=x` is not two parameters — the second `?` has no special meaning in a query string, so the whole thing becomes the literal value of `product`. Use `?product=A&email=x`.

### Supported query parameters

| Parameter   | Default (from env)        | Overridable via URL?                          |
|-------------|----------------------------|------------------------------------------------|
| `product`   | `SITE_PRODUCT`              | Yes — allowlisted text, see §12                |
| `app`       | `SITE_APP`                  | Yes — allowlisted text, see §12                |
| `company`   | `SITE_COMPANY`               | Yes — allowlisted text, see §12                |
| `email`     | `SITE_EMAIL`                 | **No** — always server-controlled              |
| `version`   | `LEGAL_VERSION`              | No — server-controlled                         |
| `effective` | `LEGAL_EFFECTIVE_DATE`       | No — server-controlled                         |
| `bg`        | `#f5f6f8`                    | Yes — hex only, see §12                        |
| `card`      | `#ffffff`                    | Yes — hex only                                 |
| `text`      | `#0d1b2a`                    | Yes — hex only                                 |
| `muted`     | `#516072`                    | Yes — hex only                                 |
| `accent`    | `#0a4fc4`                    | Yes — hex only                                 |
| `border`    | `#d9dfe7`                    | Yes — hex only                                 |

Theme colors are delivered through a dedicated `/style.css?...` endpoint (not the static file), which lets the page keep a strict `style-src 'self'` Content-Security-Policy with no inline `<style>` block.

---

## 7. Local Testing (before deploy)

```bash
# Option A – direct
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

# Option B – Docker (recommended)
docker compose up --build
```

Then open:

- http://localhost:8080/privacy
- http://localhost:8080/terms
- http://localhost:8080/security

---

## 8. Health Check

Railway (and monitoring tools) can use:

```
GET /health  →  {"status": "ok"}
```

---

## 9. Caching & Rate Limiting

- Page responses are cached for **1 hour** (`Cache-Control: max-age=3600`)
- Simple IP-based rate limit: **120 requests per hour** per IP, applied to `/privacy`, `/terms`, `/security`, and `/style.css`
- **Known quirk:** `/style.css` shares the same rate-limit bucket as the pages, and every page load fetches it once. A single browser session effectively gets ~60 full page loads/hour, not 120, since each load costs 2 hits. If you want the theme stylesheet exempt from the limit, remove the `@rate_limit` decorator from `theme_css()` in `app.py`.
- Content changes rarely, so these settings are intentional, but re-check them if you start linking these pages from high-traffic apps.

---

## 10. Updating Content

1. Edit the HTML templates or `style.css`
2. Run the test suite (§13) before pushing
3. Commit and push to `main`
4. Railway automatically rebuilds and redeploys

No downtime for normal updates.

---

## 11. Troubleshooting

| Issue                        | Solution                                      |
|-----------------------------|-----------------------------------------------|
| Build fails                 | Check Dockerfile and `requirements.txt`       |
| CSS not loading             | Confirm `static/style.css` is in the image; confirm `base.html` links `theme_css`, not `url_for('static', filename='style.css', ...)` with query params — the static route ignores query strings entirely |
| Theme color not applying    | Check the value is `#rgb` or `#rrggbb`; anything else silently falls back to default |
| Product/company text not applying | Check it only uses letters, digits, spaces, and `. , & ' ( ) / _ -`, and doesn't contain words like "script" or "eval(" — these are rejected outright, see §12 |
| 502 / Application error     | Check Railway logs                            |
| Domain not working / SSL "Not Secure" | Railway issues certificates automatically via Let's Encrypt — this is not something you configure by hand. Check Settings → Networking for the domain's status, verify the CNAME and TXT records, and see the custom-domain notes in §5 (Cloudflare proxy, CAA records, apex domains) |
| Getting 429s quickly        | See the rate-limit quirk in §9                |

---

## 12. Security Notes

- Service runs as non-root user inside the container
- Multi-stage build keeps the final image small
- No secrets are required for the current version
- **Company identity (name, email) is server-controlled via environment variables, not the URL** — this was previously a vulnerability where anyone could link to your own domain with a different company name and a different contact email
- **Product/app/company URL parameters use an allowlist, not just output-escaping.** Jinja auto-escapes everything by default, so raw injected HTML/JS was never actually executable — but as a cybersecurity company, we don't want attack-shaped strings (`<script>`, `eval(...)`, `javascript:`, `onerror=`, etc.) reflected back on our own pages at all, even inertly. Values containing anything outside `A-Za-z0-9 .,&'()/_-`, or containing blocklisted keywords, are rejected outright and replaced with the server default
- **Theme colors are validated against a strict `#rgb`/`#rrggbb` regex.** No CSS injection, no `url(...)`, no `javascript:` scheme
- Security headers are set on every response: CSP (`default-src 'self'`, no inline scripts/styles), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Strict-Transport-Security` once the request is actually over HTTPS
- Plain-HTTP requests behind the proxy are redirected to HTTPS (`force_https`)
- Rate limiting + long cache reduce abuse surface
- `ProxyFix` is used so the rate limiter reads the real client IP from Railway's forwarded headers instead of a spoofable client-supplied header — make sure `PROXY_HOPS` matches your actual setup (see §5)

This has been tested against, and blocks: reflected XSS in text fields, CSS/style injection in theme fields, Jinja/SSTI probes (`{{7*7}}`), path traversal on `/static/`, TRACE method probing, and email/identity spoofing via URL. It has **not** been checked against your specific `requirements.txt` for dependency CVEs — do that separately before a production deploy.

---

## 13. Testing

A pytest suite lives at `tests/test_app.py` and exercises everything in §12 directly against the Flask app — no live server or network needed.

### Run it yourself

```bash
pip install pytest --break-system-packages   # or just `pip install pytest` in a venv
pytest tests/test_app.py -v
```

### What it covers

- All three pages load, `/` redirects to `/privacy`, `/health` returns `{"status": "ok"}`, unknown routes 404
- 9 attack payloads in `product` (`<script>`, `onerror=`, `javascript:`, `eval(...)`, SSTI, attribute breakout, backticks, case-insensitive keyword checks) all fall back to the default value
- 5 legitimate product names pass through unchanged
- The malformed-URL case from earlier (`?product=A?email=x`) is locked in as inert, not a bug
- `email` cannot be overridden via URL under any circumstance
- Valid hex colors are applied; 8 invalid color payloads (keywords, `url()`, injected declarations, `javascript:`, style/script breakout) are all rejected
- Path traversal on `/static/../app.py` is blocked
- `TRACE` requests are refused
- All security headers are present; HSTS only appears on secure requests
- Plain-HTTP requests behind the proxy redirect to HTTPS
- Rate limiting triggers a 429 after 120 hits, and the shared `/style.css` bucket quirk from §9 is captured as a test so it won't silently regress

Run this before every deploy. If you change the allowlist, blocklist, or add new query parameters, add a case here first.

---

**Ready.**
Once the service is live on Railway, just update the footer links on the main OCI site to point to `https://legal.roosecure.com/...`.