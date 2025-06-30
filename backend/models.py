from pydantic import BaseModel
from typing import List
from datetime import datetime

class SlotRequest(BaseModel):
    start: datetime
    end: datetime
    duration: int = 30  # minutes

class BookRequest(BaseModel):
    start: datetime
    end: datetime
    title: str = "TailorTalk Meeting"

class SlotResponse(BaseModel):
    slots: List[str]

class BookResponse(BaseModel):
    success: bool
    event_link: str
