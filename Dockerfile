FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV MY_NETWORK_ADDRESS="0.0.0.0:8000"
ENV DATABASE_URL="db/block.sqlite"
ENV SEED_NODES='[]'

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
