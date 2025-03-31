FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "src.main"]
