FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

COPY backend /app/backend
COPY deploy/backend-entrypoint.sh /app/deploy/backend-entrypoint.sh
RUN chmod +x /app/deploy/backend-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/deploy/backend-entrypoint.sh"]
CMD ["gunicorn", "gstflow.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
