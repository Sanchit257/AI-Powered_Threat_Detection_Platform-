FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends bash netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY scripts/wait-for-it.sh /usr/local/bin/wait-for-it
RUN chmod +x /usr/local/bin/wait-for-it

COPY ml_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml_engine/ .

ENTRYPOINT ["/usr/local/bin/wait-for-it", "redis:6379", "--", "/usr/local/bin/wait-for-it", "db:5432", "--"]
CMD ["python", "main.py"]
