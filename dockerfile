FROM python:3.11-slim

# Set working directory to where GitHub Actions mounts the repo
WORKDIR /github/workspace

# Install dependencies from the workspace
RUN pip install --no-cache-dir -r requirements.txt

# Run the profiler script from the workspace
ENTRYPOINT ["python", "tools/pr-risk-profiler.py"]
