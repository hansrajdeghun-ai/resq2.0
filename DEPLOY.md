# Deploying / sharing resQ 2.0

The app is a single FastAPI service that serves the API **and** the web app. SQLite +
mocks by default, so it runs anywhere with no external dependencies.

## Fastest: share your local run on a phone (same Wi-Fi)
```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `http://<your-laptop-ip>:8000` on the phone (find the IP with `ipconfig getifaddr en0`).
The login page also shows the four personas — pick one per device/tab.

## Instant public link (demo to anyone): a tunnel
```bash
# with the server running on :8000
npx localtunnel --port 8000        # or: ngrok http 8000
```
Share the printed URL. Good for the jury without any hosting setup.

## Docker (reproducible)
```bash
docker build -t resq2 .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... resq2
```

## Hosted (Render — free)
1. Push this repo to GitHub.
2. Render → New → Blueprint → pick the repo (`render.yaml` is detected).
3. Set `OPENAI_API_KEY` in the dashboard. Deploy. You get a public HTTPS URL.

(Fly.io works too: `fly launch` picks up the Dockerfile; set secrets with `fly secrets set`.)

## Going live (when creds arrive)
Set these and flip `USE_MOCKS=0`:
- `KAPTURE_CHECKSUM_KEY` — enables the two B2B create (write-back) APIs
- `GOOGLE_APPLICATION_CREDENTIALS` — Pub/Sub SA key for the service-order stream
- `WHATSAPP_ACCESS_TOKEN` + `WA_PHONE_ID_*` + templates — real WhatsApp Cloud API
- Kapture reads already work with the provided Basic auth.

> Note: on a corporate laptop behind a TLS-inspecting proxy, set `KAPTURE_CA_BUNDLE`
> (see `scripts/make_ca_bundle.sh`). A clean server doesn't need it.
