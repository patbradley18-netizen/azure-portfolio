# Build #14 loader image: Python 3.12 slim, the Microsoft SQL driver's one system dependency, the loader and its contracts.
# No secrets: the job authenticates with its managed identity at run time. Published to GitHub Container Registry by Actions.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libltdl7 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY loader.py contract.py ./
COPY contracts ./contracts
USER 1000
CMD ["python", "-u", "loader.py"]
