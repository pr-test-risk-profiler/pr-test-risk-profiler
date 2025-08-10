FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pr_risk_profiler.py /app/pr_risk_profiler.py

ENTRYPOINT ["python", "/app/pr_risk_profiler.py"]