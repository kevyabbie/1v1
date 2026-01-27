FROM python:3.11.9-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies with no cache
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY discord_botv2.3.7.py .
COPY matchmaking_1v1.py .
COPY matchmaking_part1.py .


# Run the bot
CMD ["python", "discord_botv2.3.7.py"]
