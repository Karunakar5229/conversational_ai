import os
import datetime
import pytz
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- Configuration ---
TIMEZONE = 'Asia/Kolkata'
tz = pytz.timezone(TIMEZONE)
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_PATH = os.path.join("credentials", "credentials.json")  # Adjust if needed

# --- Calendar Service Setup ---
def get_calendar_service():
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        raise RuntimeError(f"❌ Failed to load Google Calendar service: {e}")

# --- Get Available Time Slots ---
def get_available_slots(start_datetime, end_datetime, duration_minutes=30):
    service = get_calendar_service()
    if start_datetime.tzinfo is None:
        start_datetime = tz.localize(start_datetime)
    if end_datetime.tzinfo is None:
        end_datetime = tz.localize(end_datetime)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_datetime.isoformat(),
        timeMax=end_datetime.isoformat(),
        timeZone=TIMEZONE,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    busy_times = [
        (
            datetime.datetime.fromisoformat(e['start']['dateTime']),
            datetime.datetime.fromisoformat(e['end']['dateTime'])
        )
        for e in events if 'dateTime' in e['start']
    ]

    slots = []
    current = start_datetime
    while current + datetime.timedelta(minutes=duration_minutes) <= end_datetime:
        overlap = any(
            start < current + datetime.timedelta(minutes=duration_minutes) and end > current
            for start, end in busy_times
        )
        if not overlap:
            slots.append(current)
        current += datetime.timedelta(minutes=duration_minutes)

    return slots

# --- Book an Event ---
def book_event(start_time, end_time, user_input: str):
    service = get_calendar_service()
    if start_time.tzinfo is None:
        start_time = tz.localize(start_time)
    if end_time.tzinfo is None:
        end_time = tz.localize(end_time)

    event = {
        'summary': f"📅 {user_input}",
        'description': f"Scheduled via TailorTalk.\n\nUser said: \"{user_input}\"",
        'start': {'dateTime': start_time.isoformat(), 'timeZone': TIMEZONE},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': TIMEZONE},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')
