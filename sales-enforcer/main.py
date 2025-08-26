# main.py
from fastapi import FastAPI, Request, Response
from celery_worker import process_pipedrive_event

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Sales Enforcer is running!"}

@app.post("/webhook/pipedrive")
async def pipedrive_webhook(request: Request):
    payload = await request.json()
    
    # Asynchronously trigger the Celery task
    process_pipedrive_event.delay(payload)
    
    # Immediately return a 200 OK to Pipedrive
    return Response(status_code=200)