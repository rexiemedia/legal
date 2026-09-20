const LEGAL_BASE_URL = "https://legal.roosecure.com";

export async function loadLegalManifest() {
  const response = await fetch(`${LEGAL_BASE_URL}/latest/company-manifest.json`, {
    cache: "no-cache",
    headers: { "Accept": "application/json" }
  });
  if (!response.ok) throw new Error(`Legal manifest HTTP ${response.status}`);
  return response.json();
}

export async function loadCompanyDocument(type) {
  const manifest = await loadLegalManifest();
  const entry = manifest.company_documents[type];
  if (!entry) throw new Error(`Unknown legal document: ${type}`);

  const response = await fetch(LEGAL_BASE_URL + entry.path, {
    cache: "force-cache",
    headers: { "Accept": "application/json" }
  });
  if (!response.ok) throw new Error(`Legal document HTTP ${response.status}`);
  return response.json();
}
