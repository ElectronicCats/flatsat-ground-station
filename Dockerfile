FROM python:3.11-slim

WORKDIR /app

# System deps for pyudev (USB device discovery)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libudev-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "-m", "webapp.app"]
