from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

from backend.calendar_utils import get_available_slots, book_event
from backend.agent import run_agent  # LangGraph agent

app = FastAPI(title="Conversational AI Agent API", version="1.0.0")

# -----------------------------
# 🌐 Enable CORS (Frontend <--> Backend)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use your Streamlit domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# ✅ Root Endpoint for Render Health Check
# -----------------------------
@app.get("/")
def root():
    return {"message": "🎯 Conversational AI Agent backend is live!"}

# -----------------------------
# 📅 Calendar Booking APIs
# -----------------------------

class SlotRequest(BaseModel):
    start: datetime
    end: datetime
    duration: int = 30

class SlotResponse(BaseModel):
    slots: List[str]

@app.post("/get-available-slots", response_model=SlotResponse)
def get_slots(request: SlotRequest):
    try:
        slots = get_available_slots(request.start, request.end, request.duration)
        return {"slots": [s.isoformat() for s in slots]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BookRequest(BaseModel):
    start: datetime
    end: datetime
    title: str = "TailorTalk Meeting"

class BookResponse(BaseModel):
    success: bool
    event_link: str

@app.post("/book-slot", response_model=BookResponse)
def book_slot(request: BookRequest):
    try:
        link = book_event(request.start, request.end, request.title)
        return {"success": True, "event_link": link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# 🤖 Conversational AI Chat API
# -----------------------------

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        reply = run_agent(request.message)
        return {"response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))