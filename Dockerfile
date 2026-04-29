FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/how-about-us/ai-server"
LABEL org.opencontainers.image.description="Travel AI FastAPI server"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
