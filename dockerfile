FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for faster builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything into container
COPY . /app

# Run your Python script when container starts
ENTRYPOINT ["python", "tools/pr_risk_profiler.py"]
