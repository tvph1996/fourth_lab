FROM python:3.11-slim
WORKDIR /app

# there are conflicts between grpc & opentelemetry libraries that leads to version downgrade and rebuilt since binary not available
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY myitems.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. myitems.proto

COPY grpc_service.py .

EXPOSE 50051
EXPOSE 9103
CMD ["python", "grpc_service.py"]
