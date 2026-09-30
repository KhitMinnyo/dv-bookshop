FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LAB_RUNTIME_DIR=/lab/runtime

WORKDIR /lab
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py test_lab.py ./

USER 10001:10001
EXPOSE 5000
CMD ["python", "app.py"]
