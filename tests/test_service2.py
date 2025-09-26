from fastapi import FastAPI
import asyncio

app = FastAPI(title="Service 2")


@app.get("/process")
async def process():
    await asyncio.sleep(2)
    return {"message": "Service 2 completed successfully"}
