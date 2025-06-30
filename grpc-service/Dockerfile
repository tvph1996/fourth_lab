FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 50051
EXPOSE 9103
CMD ["python", "grpc_service.py"]