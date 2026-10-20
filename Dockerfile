FROM python:3.12-slim

WORKDIR /app

# system deps for pillow/qrcode wheels are already in slim; keep it minimal
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# default to mocks + sqlite; override with env (DATABASE_URL, USE_MOCKS, keys) at deploy
ENV APP_ENV=prod USE_MOCKS=1 DATABASE_URL=sqlite+aiosqlite:////app/resq.sqlite3
EXPOSE 8000

# bind 0.0.0.0 so it's reachable; honour $PORT if the host sets one (Render/Fly)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
