FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY last_update.sql ./last_update.sql

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
