FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Must stay at one worker, for the same reason as scripts/spinshare-api.service:
# chat presence and message fan-out live in process memory, so a second worker
# is an island whose members cannot see or hear the first's. It fails silently.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
