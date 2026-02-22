FROM python:3.12-slim

# Update CA certificates and install backup tooling
RUN apt-get update && \
    apt-get install -y ca-certificates default-mysql-client curl && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install supercronic for cron scheduling
RUN curl -fsSL \
    https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Ensure scripts are executable
RUN chmod +x /app/scripts/entrypoint.sh /app/scripts/backup_to_gdrive.sh

# Railway uses PORT env variable
ENTRYPOINT ["/app/scripts/entrypoint.sh"]