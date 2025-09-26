from fastapi import FastAPI
import asyncio

app = FastAPI(title="Service 1")

@app.get("/process")
async def process():
    await asyncio.sleep(5)
    return {"message": "Service 1 completed successfully"}