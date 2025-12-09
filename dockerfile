FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------------------------------------
# Install system dependencies WITHOUT filling disk
# -----------------------------------------------------
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/*

# -----------------------------------------------------
# Upgrade pip
# -----------------------------------------------------
RUN pip install --upgrade pip

# -----------------------------------------------------
# Copy only requirements and install them first
# -----------------------------------------------------
COPY requirements.txt /app/

# First install mysqlclient wheel if available
RUN pip install --no-cache-dir --prefer-binary mysqlclient

# Install full requirements
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# -----------------------------------------------------
# Copy full project
# -----------------------------------------------------
COPY . /app/

# -----------------------------------------------------
# Collect static files
# -----------------------------------------------------
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 8000 PerfumeValley.asgi:application"]

