FROM python:3.11-slim

# System deps needed by Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libxkbcommon0 libgtk-3-0 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxfixes3 libdrm2 libgbm1 libasound2 libpangocairo-1.0-0 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 libxrandr2 libxshmfence1 \
    fonts-liberation libu2f-udev ca-certificates wget && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright + browser
RUN python -m playwright install --with-deps chromium

COPY . /app

ENV TZ=Europe/Copenhagen \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]