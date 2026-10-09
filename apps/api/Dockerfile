# Krinea API (also used for the worker: override the command)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 KRINEA_ENV=production DATA_DIR=/data
WORKDIR /app
COPY packages/core /app/packages/core
COPY apps/api /app/apps/api
RUN pip install -e /app/packages/core -e /app/apps/api
RUN mkdir -p /data
WORKDIR /app/apps/api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'))" || exit 1
CMD uvicorn krinea_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"
