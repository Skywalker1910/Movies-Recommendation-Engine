FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 and scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=run.py

# Gunicorn: 2 workers keeps memory under ~800MB on t3.micro (1GB RAM)
# Timeout 120s allows lazy ML model loading on first request
CMD ["gunicorn", "run:application", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--preload", \
     "--timeout", "120", \
     "--access-logfile", "-"]
