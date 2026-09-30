FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /lab
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py storage_client.py storage_gateway.py test_lab.py ./
COPY static ./static
COPY seed ./seed

USER 10001:10001
EXPOSE 5000
CMD ["python", "app.py"]
