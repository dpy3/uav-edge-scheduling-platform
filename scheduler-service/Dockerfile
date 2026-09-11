FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api.py baselines.py metrics.py problem.py solve_cpsat.py solve_ga.py ./
COPY tests ./tests

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
