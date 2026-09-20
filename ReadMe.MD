# ROO Secure Legal Distribution Service

Version: 2026-09-20

This package is a static, versioned legal-document distribution layer for ROO Secure IT Solutions web and mobile applications.

## Architecture

Recommended public hostname:

`https://legal.roosecure.com`

The service should contain **static files only** wherever practical:

- JSON legal documents
- immutable versioned paths
- a small `latest/company-manifest.json`
- optional human-readable HTML copies
- optional integrity hashes/signatures

Do not put authentication, an admin dashboard, a database, application secrets, customer data, payment data, or application control/configuration in this service.

The goal is to keep the legal-document serving layer separate from the main ROO Secure application infrastructure.

## Directory layout

```text
roo-secure-legal-cloud/
├── README.md
├── schema/
│   └── legal-document.schema.json
├── v1/
│   ├── company/
│   │   ├── privacy/2026-09-20.json
│   │   ├── terms/2026-09-20.json
│   │   ├── cookies/2026-09-20.json
│   │   ├── data-compliance/2026-09-20.json
│   │   └── refunds/2026-09-20.json
│   └── apps/
│       └── example-app/
│           ├── privacy/2026-09-20.json
│           └── terms/2026-09-20.json
├── latest/
│   ├── company-manifest.json
│   └── hashes.sha256.json
├── html/
│   ├── privacy.html
│   ├── terms.html
│   ├── cookies.html
│   ├── data-compliance.html
│   ├── refunds.html
│   └── style.css
└── examples/
    ├── web/
    └── mobile/
```

## Important legal model

Use a **master policy + application-specific notice** model.

The company-level documents describe common ROO Secure practices. Each application should have its own supplement whenever it collects different data, uses different vendors, has different retention, has different payment flows, or is operated by a different legal entity.

Do not publish a statement that a particular vendor, tracking technology, payment processor, CAPTCHA provider, advertising platform, retention period, transfer mechanism or legal basis is used unless that is actually true for the application.

GDPR transparency requires organisations to explain matters such as purposes, categories, legal basis, retention, recipients, international transfers and individual rights where applicable. Controller/processor roles also need to be determined from the actual processing relationship.

## Deployment recommendation

A suitable deployment pattern is:

```text
                 Internet
                    |
              Cloudflare/CDN
                    |
          legal.roosecure.com
                    |
             Static object store
                    |
        immutable JSON/HTML files
```

The origin can be an object-storage bucket or a minimal static web server. No Flask, Node API, database or Redis is required.

### Option A — Object storage + CDN

Recommended for the lowest application attack surface.

1. Create a dedicated storage bucket.
2. Upload this directory.
3. Put a CDN in front of the bucket.
4. Configure HTTPS for `legal.roosecure.com`.
5. Allow public `GET`/`HEAD` only.
6. Block public write/delete operations.
7. Publish new legal versions by adding new immutable files.
8. Update the manifest only after the new documents are validated.
9. Keep old versions available.

### Option B — Static NGINX server

If you prefer your own infrastructure:

```nginx
server {
    listen 443 ssl http2;
    server_name legal.roosecure.com;

    root /srv/legal;

    location / {
        try_files $uri =404;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header X-Frame-Options "DENY" always;
        add_header Content-Security-Policy "default-src 'none'; frame-ancestors 'none'; base-uri 'none'" always;
    }

    location ~* \.json$ {
        default_type application/json;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }

    location = /latest/company-manifest.json {
        add_header Cache-Control "public, max-age=300, must-revalidate" always;
    }
}
```

Adjust TLS, certificate, DNS and origin settings to your actual environment.

OWASP recommends security response headers such as `X-Content-Type-Options: nosniff`, appropriate referrer policy and carefully configured CSP/HSTS. HSTS should only be enabled with a long lifetime after confirming all relevant subdomains are HTTPS-ready.

## Cache strategy

Use different caching policies:

### Immutable versioned documents

Example:

`/v1/company/privacy/2026-09-20.json`

Use:

```text
Cache-Control: public, max-age=31536000, immutable
```

Because the filename contains the document version, it should never be overwritten.

### Latest manifest

Example:

`/latest/company-manifest.json`

Use a short cache/revalidation period such as:

```text
Cache-Control: public, max-age=300, must-revalidate
```

The exact value can be changed to match your release process.

## Application integration

Applications should:

1. Fetch the manifest.
2. Determine the exact document version.
3. Fetch the immutable document.
4. Validate the JSON schema if desired.
5. Cache the verified document locally.
6. Continue using the last verified copy if the legal service is temporarily unavailable.
7. Display the effective date and version.
8. Record the exact version accepted when a user accepts terms, where your product requires acceptance records.

Do not make normal application startup dependent on a live legal-server request.

### Web example

```javascript
const BASE = "https://legal.roosecure.com";

async function getLegalManifest() {
  const r = await fetch(`${BASE}/latest/company-manifest.json`, {
    cache: "no-cache"
  });
  if (!r.ok) throw new Error("Legal manifest unavailable");
  return r.json();
}

async function getPrivacyPolicy() {
  const manifest = await getLegalManifest();
  const path = manifest.company_documents.privacy.path;

  const r = await fetch(BASE + path, {
    cache: "force-cache"
  });
  if (!r.ok) throw new Error("Privacy policy unavailable");

  return r.json();
}
```

For production, add local caching, schema validation and error handling rather than making every page load dependent on the network.

### Mobile example

The mobile application should ship with a last-known verified legal version or a safe fallback copy. On connectivity, it can check the manifest and refresh its cached copy.

Do not block a user from opening the application solely because `legal.roosecure.com` is unavailable.

## Integrity and signatures

This package includes SHA-256 hashes as an integrity mechanism.

Important distinction:

**A hash detects accidental changes only when the trusted hash itself comes from a trusted source.**

For stronger authenticity, add a digital signature system such as Ed25519:

```text
legal document
      |
      +--> SHA-256
      |
      +--> Ed25519 signature
                    |
             trusted public key
             in release process
```

For mobile applications, the trusted public key can be embedded in the application and rotated through a documented key-rotation process.

Do not hard-code a private signing key in a mobile application, web application or public server.

## Publishing workflow

Recommended release process:

```text
Edit legal source
      |
Legal/compliance review
      |
Application data-flow review
      |
Validate JSON schema
      |
Generate hashes
      |
Sign release (recommended)
      |
Upload immutable version
      |
Verify CDN/object-storage response
      |
Update latest manifest
      |
Smoke-test all applications
```

Never overwrite an existing versioned document.

## Security boundaries

The legal distribution service should be treated as public content.

It should NOT contain:

- passwords
- API keys
- private signing keys
- customer information
- support tickets
- payment information
- internal infrastructure details
- application secrets
- feature flags
- remote execution instructions
- arbitrary HTML submitted by users

Keep the legal service read-only from the public Internet.

## CORS

For JSON consumption by browser applications, configure CORS only for the origins that actually need cross-origin access.

Example:

```text
Access-Control-Allow-Origin: https://www.roosecure.com
Vary: Origin
```

For multiple applications, explicitly list their production origins rather than using `*` unless there is a documented reason to allow unrestricted cross-origin reads.

Mobile applications generally do not rely on browser CORS rules.

## Robots and indexing

Legal pages are public documents. If you want search engines to index the human-readable HTML, allow indexing.

If you want only the main ROO Secure website to rank the legal pages, you can use appropriate canonical URLs and crawler directives.

JSON endpoints do not need to be treated as an application API.

## Versioning

Use immutable dates or semantic versions.

Example:

```text
/v1/company/privacy/2026-09-20.json
/v1/company/privacy/2026-10-15.json
```

or:

```text
/v1/company/privacy/1.1.0.json
/v1/company/privacy/1.2.0.json
```

The version should change whenever the published legal content materially changes.

## Application identifiers

Replace:

`example-app`

with stable application IDs, for example:

```text
apps/
├── roo-client-portal/
├── roo-mobile/
├── roo-scanner/
└── roo-support/
```

Each application can have its own privacy and terms documents while still referencing the company-wide policies.

## Central legal URLs

Once deployed, your applications can use stable human-readable URLs such as:

```text
https://legal.roosecure.com/privacy
https://legal.roosecure.com/terms
https://legal.roosecure.com/cookies
https://legal.roosecure.com/data-compliance
https://legal.roosecure.com/refunds
```

Those routes should resolve to the current approved HTML version.

For contractual records, store the exact immutable version rather than only storing `/latest`.

## Legal review

The included documents are structured templates, not legal advice and not proof of compliance.

Before production publication, verify:

- exact legal entity name
- controller/processor role for each application
- countries served
- actual data categories
- actual analytics SDKs
- actual crash-reporting provider
- actual CAPTCHA provider
- actual payment processor
- actual advertising/remarketing providers
- actual retention periods
- actual data locations
- international transfer mechanisms
- California applicability
- CalOPPA applicability
- Canadian privacy-law applicability
- GDPR/UK GDPR applicability
- children's privacy requirements
- refund/cancellation rules
- applicable governing law
- data-subject request workflow

This is especially important because privacy compliance depends on the actual processing activities rather than merely listing legal frameworks.

## Pre-launch checklist

- [ ] Legal entity confirmed
- [ ] Privacy contact confirmed
- [ ] Vendor inventory completed
- [ ] Data inventory completed
- [ ] Retention schedule completed
- [ ] Application-specific notices completed
- [ ] Payment flow reviewed
- [ ] Analytics reviewed
- [ ] Crash logging reviewed
- [ ] Remarketing reviewed
- [ ] CAPTCHA reviewed
- [ ] Cookie/consent mechanism reviewed
- [ ] GDPR rights workflow tested
- [ ] California rights workflow tested where applicable
- [ ] Security headers deployed
- [ ] HTTPS verified
- [ ] Public write access disabled
- [ ] Versioned files immutable
- [ ] Hashes generated
- [ ] Digital signing implemented if required
- [ ] CDN cache tested
- [ ] Offline/mobile fallback tested
- [ ] Terms acceptance version logging tested
- [ ] Old versions remain retrievable
- [ ] Legal counsel/compliance review completed

## Source guidance

Security configuration in this README follows general OWASP guidance for HTTP security headers, CSP, HSTS and REST responses.

Privacy structure is designed around commonly applicable GDPR concepts including transparency, purpose limitation, data minimisation, storage limitation, integrity/confidentiality, accountability, and controller/processor responsibilities.

Always verify current law and regulator guidance before publication.

## Contact

ROO Secure IT Solutions  
https://www.roosecure.com  
privacy@roosecure.com  
info@roosecure.com
