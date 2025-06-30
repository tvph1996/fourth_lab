FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the proto file and generate the python files from it
COPY myitems.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. myitems.proto

# Copy ONLY the main application file, NOT everything.
COPY grpc_service.py .

EXPOSE 50051
EXPOSE 9103
CMD ["python", "grpc_service.py"]
