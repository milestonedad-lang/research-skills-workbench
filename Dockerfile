FROM node:24-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build
FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY server ./server
COPY catalog ./catalog
COPY --from=web /build/dist ./web/dist
ENV WORKBENCH_DATA=/app/data PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8765"]
