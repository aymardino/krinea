# Systematic review workbench — single container, data persisted in /data
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data STREAMLIT_SERVER_HEADLESS=true STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py ./
COPY .streamlit ./.streamlit

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; import os; urllib.request.urlopen('http://localhost:%s/_stcore/health' % os.environ.get('PORT', '8501'))" || exit 1

CMD streamlit run review_app.py --server.port=${PORT:-8501} --server.address=0.0.0.0
