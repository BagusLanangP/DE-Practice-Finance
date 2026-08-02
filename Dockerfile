FROM python:3.12-slim

WORKDIR /app

# Install system build dependencies for psycopg2 and PostgreSQL connection
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files into container
COPY . .

# Default command: Generate synthetic raw data, then execute ETL pipeline
CMD ["sh", "-c", "python scripts/generate_data.py && python scripts/etl_pipeline.py"]
