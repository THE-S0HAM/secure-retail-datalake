FROM python:3.11-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pipeline.py database.py validation.py health_check.py backup_database.py ./
COPY pytest.ini ./
COPY tests/ ./tests/
CMD ["python", "pipeline.py"]
