#!/usr/bin/env bash
# Build a CA bundle for machines behind a TLS-inspecting SASE proxy
# (e.g. Check Point Harmony SASE / "fyndsecure"), which re-signs HTTPS with a
# corporate root that lives in the macOS Keychain but not in certifi.
#
# Produces resq_ca_bundle.pem = certifi roots + macOS system + system-root certs.
# Then set KAPTURE_CA_BUNDLE=resq_ca_bundle.pem in .env.
#
# On a clean server with the real Reliance certificate you do NOT need this —
# leave KAPTURE_CA_BUNDLE empty to use certifi.
set -euo pipefail
cd "$(dirname "$0")/.."

CERTIFI="$(python -c 'import certifi; print(certifi.where())')"
OUT="resq_ca_bundle.pem"

cat "$CERTIFI" > "$OUT"
security find-certificate -a -p /Library/Keychains/System.keychain >> "$OUT" 2>/dev/null || true
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> "$OUT" 2>/dev/null || true

echo "wrote $OUT ($(grep -c 'BEGIN CERT' "$OUT") certificates)"
echo "set KAPTURE_CA_BUNDLE=$OUT in .env"
