FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
RUN useradd --system --uid 10001 app && mkdir /data && chown 10001 /data
USER 10001
ENV GATEWAY_DB=/data/gateway.db
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
