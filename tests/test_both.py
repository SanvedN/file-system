import time
from fastapi import FastAPI, Request
import httpx
import asyncio

app = FastAPI()

SERVICE_MAP = {
    "service1": "http://localhost:8001/process",
    "service2": "http://localhost:8002/process",
}


@app.get("/route/{service_name}")
async def route_to_service(service_name: str, request: Request):
    url = SERVICE_MAP.get(service_name)

    if not url:
        return {"error": "Service not found"}

    async with httpx.AsyncClient() as client:
        print(f"Routing to {url}")
        response = await client.get(url)
        return response.json()


@app.get("/parallel")
async def parallel_requests():
    async with httpx.AsyncClient() as client:
        # Fire off both requests at once
        tasks = [
            client.get(SERVICE_MAP["service1"]),
            client.get(SERVICE_MAP["service2"]),
        ]
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]


@app.get("/run-both")
async def run_both_services():
    start_time = time.monotonic()

    async with httpx.AsyncClient() as client:
        # Create tasks for both service calls
        task1 = client.get(SERVICE_MAP["service1"])
        task2 = client.get(SERVICE_MAP["service2"])

        # Run them concurrently
        response1, response2 = await asyncio.gather(task1, task2)

    end_time = time.monotonic()
    duration = end_time - start_time  # in seconds

    return {
        "service1_response": response1.json(),
        "service2_response": response2.json(),
        "duration_seconds": round(duration, 2),
    }
