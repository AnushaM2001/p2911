# -----------------------------
# Base Image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# -----------------------------
# Install system dependencies (WeasyPrint, Pillow, MySQL, fonts, etc.)
# -----------------------------
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
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-dejavu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/*

# -----------------------------
# Upgrade pip
# -----------------------------
RUN pip install --upgrade pip

# -----------------------------
# Copy only requirements first
# -----------------------------
COPY requirements.txt /app/

# Install MySQL client first (prefer binary wheels)
RUN pip install --no-cache-dir --prefer-binary mysqlclient

# Install all other requirements
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# -----------------------------
# Copy full project
# -----------------------------
COPY . /app/

# -----------------------------
# Collect static files
# -----------------------------
RUN python manage.py collectstatic --noinput

# Expose port for Daphne/ASGI server
EXPOSE 8000

# -----------------------------
# Run migrations and start server
# -----------------------------
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 8000 PerfumeValley.asgi:application"]
