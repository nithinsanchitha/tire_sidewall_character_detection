FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements.txt
COPY backend/app /app/backend/app
COPY references /app/references
COPY scripts /app/scripts
ENV PYTHONPATH=/app/backend HF_HOME=/app/models/huggingface
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
