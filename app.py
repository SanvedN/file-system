from fastapi import FastAPI, status

app = FastAPI()


@app.get("/")
async def root() -> dict:
    return {"main_app": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> str:
    return "PONG"
