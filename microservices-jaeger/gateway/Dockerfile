FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*
COPY ../requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway .
EXPOSE 8080
CMD ["python3", "app.py"]