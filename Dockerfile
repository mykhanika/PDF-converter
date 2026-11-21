FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libreoffice-writer libreoffice-calc libreoffice-impress fonts-dejavu \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY app.py ui.html ./
COPY static ./static
ENV PDFTK_WORK=/tmp/pdftk PORT=5000
EXPOSE 5000
# One worker: sessions live on local disk. Threads handle concurrent requests.
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 1 --threads 8 --timeout 300 app:app"]
