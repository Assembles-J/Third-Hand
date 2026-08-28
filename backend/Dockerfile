FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org
ARG PIP_TIMEOUT=120
ARG PIP_RETRIES=5

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --timeout "${PIP_TIMEOUT}" \
    --retries "${PIP_RETRIES}" \
    --index-url "${PIP_INDEX_URL}" \
    --trusted-host "${PIP_TRUSTED_HOST}" \
    -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
