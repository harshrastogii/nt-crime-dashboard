FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Build the cleaned data at image-build time so the app starts fast.
# prepare_data.py auto-discovers CSVs in ./data (or the root).
RUN python prepare_data.py

# Hugging Face Spaces expects the app on port 7860
EXPOSE 7860
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:server"]
