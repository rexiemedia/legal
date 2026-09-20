# Mobile integration

Use the same immutable JSON documents as the web application.

Recommended behaviour:

1. Bundle a last-known approved document/version with the release.
2. Fetch the latest manifest when network access is available.
3. Download the immutable document.
4. Validate its schema and, if implemented, its cryptographic signature.
5. Cache the verified document.
6. Fall back to the last verified copy if the legal service is unavailable.
7. Record the exact accepted document version when your acceptance flow requires an audit record.

Do not make application startup depend on the legal service being online.
