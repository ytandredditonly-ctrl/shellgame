FROM python:3.12-slim
COPY app.py /opt/app.py
EXPOSE 80
# Stdlib only — no pip needed. Deliberately vulnerable; local arena use only.
CMD ["python3", "/opt/app.py"]
