FROM python:3.11-slim-bookworm

# .pyc 바이트코드 생성 방지
ENV PYTHONDONTWRITEBYTECODE=1
# 표준출력 버퍼링하지 않
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "mkdir -p /data/assets && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
