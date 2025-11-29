FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for mysqlclient, reportlab, pillow, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    pkg-config \
    libmariadb-dev \
    libmariadb-dev-compat \
    libfreetype6-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    zlib1g-dev \
    libx11-dev \
    libxcb1-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest
RUN pip install --upgrade pip

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/

# Install mysqlclient first with prefer-binary to get wheel if available
RUN pip install --no-cache-dir --prefer-binary mysqlclient

# Install rest of the requirements with prefer-binary for speed
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy rest of your app
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "python manage.py makemigrations && python manage.py migrate && daphne -b 0.0.0.0 -p 8000 PerfumeValley.asgi:application"]

