FROM python:3.11-slim

WORKDIR /github/workspace

# Install git so subprocess calls work
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy our tool and requirements to a separate directory
COPY requirements.txt /app/
COPY tools/pr-risk-profiler.py /app/tools/

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Run the Python script when container starts
# Note: We use the full path to our script but work from the mounted workspace
ENTRYPOINT ["python", "/app/tools/pr-risk-profiler.py"]
