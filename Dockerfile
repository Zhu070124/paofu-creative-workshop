FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8922 8923

# Default token — override with -e WORKSHOP_TOKEN=... at runtime
ENV WORKSHOP_TOKEN=paofu-workshop-2026

CMD ["python", "server.py"]
