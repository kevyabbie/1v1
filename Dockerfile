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
COPY discordbot.py .
COPY ghost_player_commands.py .
COPY railway_backup.py .
COPY team_matchmaking_1v1.py .
COPY team_matchmaking_part1.py .
COPY team_matchmaking_part2.py .
COPY team_matchmaking_part3.py .
COPY team_matchmaking_part6.py .
COPY team_matchmaking_part7.py .
COPY team_matchmaking_part8.py .
COPY team_matchmaking_part9.py .
COPY team_matchmaking_part10.py .
COPY team_matchmaking_part11.py .
COPY team_matchmaking_part12.py .
COPY team_matchmaking_part13.py .
COPY team_matchmaking_part14.py .



# Run the bot
CMD ["python", "discordbot.py"]
