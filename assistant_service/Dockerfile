FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "src/main.py"]
