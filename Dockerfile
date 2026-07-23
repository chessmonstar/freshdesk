FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + bundled retrieval index
COPY . .

# Cloud Run provides $PORT (defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# One worker is plenty for this low-volume webhook; Cloud Run adds instances under load.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
