import os
import logging
import grpc
from fastapi import FastAPI, HTTPException, Request, Response # type: ignore
import uvicorn # type: ignore
import myitems_pb2
import myitems_pb2_grpc
from pybreaker import CircuitBreaker, CircuitBreakerError # type: ignore
import asyncio
import json
import warnings
import time
from prometheus_client import Counter, Histogram, generate_latest

# --- OpenTelemetry Imports ---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient



warnings.filterwarnings("ignore", category=DeprecationWarning)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- OpenTelemetry Setup ---

resource = Resource(attributes={
    "service.name": "rest-service"
})

# Set up a TracerProvider
provider = TracerProvider(resource=resource)

# Set up a BatchSpanProcessor and OTLPSpanExporter
# Sends traces to the OTel Collector endpoint configured in docker-compose.yml
otlp_exporter = OTLPSpanExporter(
    endpoint="otel-collector:4317",
    insecure=True
)
processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(processor)

# Sets the global default tracer provider
trace.set_tracer_provider(provider)

# Instrument the gRPC client to automatically create spans for outgoing calls
GrpcInstrumentorClient().instrument()



app = FastAPI()



# Prometheus Metrics
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"]
)

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)



# --- Record Metrics for FastAPI REST-service ---

# Worker to collect data from all requests
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    endpoint = request.url.path

    # Group paths like /items/{item_id}
    if request.scope.get('root_path'):
         endpoint = request.scope['root_path'] + endpoint

    REQUEST_LATENCY.labels(request.method, endpoint).observe(process_time)

    REQUEST_COUNTER.labels(request.method, endpoint, response.status_code).inc()

    return response

# Expose collected data
@app.get("/metrics", status_code=200)
def metrics():
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")



# gRPC Setup
GRPC_HOST = os.getenv("GRPC_HOST", "localhost")
GRPC_PORT = os.getenv("GRPC_PORT", "50051")
GRPC_ADDRESS = f"{GRPC_HOST}:{GRPC_PORT}"

gRPC_channel = grpc.insecure_channel(GRPC_ADDRESS)
gRPC_methods = myitems_pb2_grpc.ItemServiceStub(gRPC_channel)



# Circuit Breaker Setup
breaker = CircuitBreaker(fail_max=3, reset_timeout=6)
MAX_RETRIES = 2



# --- FastAPI REST-server Setup ---

@app.post("/items")
async def add_item(request: Request):

    global gRPC_channel, gRPC_methods
    delay = 1
    body = await request.json()
    item_id = body.get("id")
    name = body.get("name")
    
    if not all([isinstance(item_id, int), name]):
        raise HTTPException(status_code=400, detail="Request must include 'id' and 'name'.")

    grpc_request = myitems_pb2.Item(id=item_id, name=name) # type: ignore

    for attempt in range(MAX_RETRIES + 1):

        try:
            
            if breaker.current_state == 'CLOSED':
                
                response = breaker.call(gRPC_methods.AddItem, grpc_request, timeout=1.0)
            
            else:
                
                # Only create new channel when CircuitBreaker is HALF_OPEN
                gRPC_new_channel = grpc.insecure_channel(GRPC_ADDRESS)
                gRPC_methods = myitems_pb2_grpc.ItemServiceStub(gRPC_new_channel)
                response = breaker.call(gRPC_methods.AddItem, grpc_request, timeout=1.0)
            
            
            if response.result:
                
                content = {"message": "Item added successfully.", "item": {"id": response.added_item.id, "name": response.added_item.name}}
                return Response(content=json.dumps(content) + "\n", status_code=201, media_type="application/json")

            else:
                raise HTTPException(status_code=409, detail="Item with ID or name already exists.")
                

        except (CircuitBreakerError):

            content = {
                "status": "error",
                "message": "Service unavailable. The circuit breaker is open. Please try again later."
            }
            logging.warning(f"gRPC-service unavailable. Calls will no longer be accepted. Please try again later. {body}")
            return Response(content=json.dumps(content) + "\n", status_code=503, media_type="application/json")           


        except grpc.RpcError as err:
            
            logging.warning(f"Call {attempt + 1} failed")
            await asyncio.sleep(delay)
            delay *= 2
    
    

@app.get("/items/")
def get_items(item_id: int = 0, name: str = ""):

    try:

        if not item_id and not name:
            raise HTTPException(status_code=400, detail="Provide 'id' or 'name'.")

        with grpc.insecure_channel(GRPC_ADDRESS) as channel:
            stub = myitems_pb2_grpc.ItemServiceStub(channel)
            request = myitems_pb2.Item(id=item_id, name=name)
            responses = stub.GetItem(request, timeout=2.0)
            results = [{"id": resp.requested_item.id, "name": resp.requested_item.name} for resp in responses if resp.result]

            if not results:
                raise HTTPException(status_code=404, detail="No items found.")

            return {"message": "Items retrieved successfully.", "items": results}


    except grpc.RpcError as e:

        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())

        else:
            raise HTTPException(status_code=500, detail=f"gRPC-service failure: {e.details()}")


@app.put("/items/{item_id}")
async def update_item(item_id: int, request: Request):

    try:
        body = await request.json()
        new_name = body.get("name")

        if not new_name:
            raise HTTPException(status_code=400, detail="The 'name' field is required in the request body.")

        with grpc.insecure_channel(GRPC_ADDRESS) as channel:
            stub = myitems_pb2_grpc.ItemServiceStub(channel)
            item_to_update = myitems_pb2.Item(id=item_id, name=new_name)
            response = stub.UpdateItem(item_to_update, timeout=2.0)

            if response.result:
                return {"message": f"Item {item_id} updated successfully.", "old_item": {"id": response.old_item.id, "name": response.old_item.name}, "new_item": {"id": response.new_item.id, "name": response.new_item.name}}


    except grpc.RpcError as e:

        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())

        elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail=e.details())

        else:
            raise HTTPException(status_code=500, detail=f"gRPC-service failure: {e.details()}")


@app.delete("/items/{item_id}", status_code=200)
def delete_item(item_id: int):
    try:

        with grpc.insecure_channel(GRPC_ADDRESS) as channel:
            stub = myitems_pb2_grpc.ItemServiceStub(channel)
            request = myitems_pb2.Item(id=item_id)
            response = stub.DeleteItem(request, timeout=2.0)

            if response.result:
                return {"message": "Successfully deleted item.", "deleted_item": {"id": response.deleted_item.id, "name": response.deleted_item.name}}


    except grpc.RpcError as e:

        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())

        else:
            raise HTTPException(status_code=500, detail=f"gRPC-service failure: {e.details()}")



# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)



# Startup
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
