FROM python:3.12-slim
COPY serve.py /opt/serve.py
# Ports are declared per-service via SQ_PORTS in compose.yaml.
CMD ["python3", "/opt/serve.py"]
