The file **does exist**. It’s here:

**`legal-service/read-railway-deploy.md`**

Full contents:

```markdown
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
│   └── style.css
├── templates/
│   ├── base.html
│   ├── privacy.html
│   ├── terms.html
│   └── security.html
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

Railway will build the multi-stage Docker image and start the service.

---

## 5. Configure the Service

### Environment (optional)

No environment variables are required for the basic setup.  
You can later add:

| Variable       | Purpose                          | Example                  |
|----------------|----------------------------------|--------------------------|
| `PORT`         | Railway sets this automatically  | `8080`                   |

### Custom Domain

1. Open your service on Railway
2. Go to **Settings → Domains**
3. Click **Custom Domain**
4. Add: `legal.roosecure.com`
5. Create the CNAME record that Railway shows you at your DNS provider

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

```
https://legal.roosecure.com/privacy?product=ROO%20Mobile&app=ios
https://legal.roosecure.com/terms?product=ClientPortal&company=ROO%20Secure%20IT%20Solutions
https://legal.roosecure.com/security?product=AgentLab&accent=%23ff6b6b
```

### Supported query parameters

| Parameter   | Default value                  | Description                    |
|-------------|--------------------------------|--------------------------------|
| `product`   | `ROO Secure`                   | Product / service name         |
| `app`       | `roosecure.com`                | Application identifier         |
| `company`   | `ROO Secure IT Solutions`      | Legal entity name              |
| `email`     | `legal@roosecure.com`          | Contact email                  |
| `version`   | `2026.09`                      | Policy version                 |
| `effective` | today’s date                   | Effective date                 |
| `bg`        | `#0b0e14`                      | Background colour              |
| `card`      | `#12161f`                      | Card background                |
| `text`      | `#e6edf3`                      | Main text colour               |
| `muted`     | `#8b949e`                      | Secondary text                 |
| `accent`    | `#58a6ff`                      | Accent / link colour           |
| `border`    | `#21262d`                      | Border colour                  |

Only hex colours (`#rgb` or `#rrggbb`) are accepted for theme parameters.

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

- Responses are cached for **1 day** (`Cache-Control: max-age=86400`)
- Simple IP-based rate limit: **120 requests per day** per IP
- Content changes rarely, so these settings are intentional

---

## 10. Updating Content

1. Edit the HTML templates or `style.css`
2. Commit and push to `main`
3. Railway automatically rebuilds and redeploys

No downtime for normal updates.

---

## 11. Troubleshooting

| Issue                        | Solution                                      |
|-----------------------------|-----------------------------------------------|
| Build fails                 | Check Dockerfile and `requirements.txt`       |
| CSS not loading             | Confirm `static/style.css` is in the image    |
| 502 / Application error     | Check Railway logs                            |
| Domain not working          | Verify CNAME and wait for DNS propagation     |
| Theme not applying          | Ensure colour starts with `#` and is valid    |

---

## 12. Security Notes

- Service runs as non-root user inside the container
- Multi-stage build keeps the final image small
- No secrets are required for the current version
- Rate limiting + long cache reduce abuse surface

---

**Ready.**  
Once the service is live on Railway, just update the footer links on the main OCI site to point to `https://legal.roosecure.com/...`.
```

---

The file is located at:

