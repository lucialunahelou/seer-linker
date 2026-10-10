FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV MEDIA_BASE=/media/movies

EXPOSE 5000

CMD ["python", "app.py"]