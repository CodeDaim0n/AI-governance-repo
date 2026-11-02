FROM python:3.12-slim
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-enterprise.txt
COPY fabric ./fabric
COPY policies ./policies
COPY docs ./docs
COPY scripts ./scripts
RUN useradd --uid 10001 --create-home fabric && mkdir -p /tmp/mlflow-artifacts && chown 10001:10001 /tmp/mlflow-artifacts
USER 10001
CMD ["uvicorn","fabric.enterprise.app:app","--host","0.0.0.0","--port","8088"]
