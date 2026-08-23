FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system bookshop \
    && adduser --system --ingroup bookshop --home /nonexistent --no-create-home bookshop

WORKDIR /opt/bookshop
COPY infra-labs/hardening/example_app.py /opt/bookshop/example_app.py

USER bookshop:bookshop
EXPOSE 8000

ENTRYPOINT ["python3"]
