# 1) сборка фронтенда
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2) приложение
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LK_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY --from=web /web/dist ./static
RUN useradd -r -u 10001 lk && chown -R lk /app
USER lk
EXPOSE 8800
# адрес клиента приложение определяет само (web.client_ip): правый публичный адрес из X-Forwarded-For от внутреннего прокси
# число воркеров — по памяти тарифа (Argon2id берёт ~64 МБ на проверку пароля)
ENV LK_WORKERS=2
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8800 --workers ${LK_WORKERS} --no-proxy-headers"]
