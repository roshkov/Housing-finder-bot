# Includes Python, Chromium, and all Playwright deps preinstalled
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY . /app

# Optional: keep logs unbuffered and set your local TZ
ENV PYTHONUNBUFFERED=1 TZ=Europe/Copenhagen

# Start your bot
CMD ["python", "main.py"]