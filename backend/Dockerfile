FROM python:3.11-slim

# Non-root user
RUN groupadd -r epsilon && useradd -r -g epsilon -u 1000 epsilon

WORKDIR /app

# Install dependencies
COPY --chown=epsilon:epsilon requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=epsilon:epsilon . .

# Create __pycache__ dir (tmpfs mount target)
RUN mkdir -p /app/__pycache__ && chown epsilon:epsilon /app/__pycache__

USER 1000

EXPOSE 8000

# Run alembic migration then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
