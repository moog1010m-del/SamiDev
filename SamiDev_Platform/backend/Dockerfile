FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 samidev
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY --chown=samidev:samidev backend /app/backend
COPY --chown=samidev:samidev game /app/game
USER samidev
WORKDIR /app/backend
CMD ["python", "app.py"]
