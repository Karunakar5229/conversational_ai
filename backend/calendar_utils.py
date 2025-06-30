import os
import pickle
import datetime
import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

TIMEZONE = 'Asia/Kolkata'
tz = pytz.timezone(TIMEZONE)
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    token_path = "token.pickle"
    creds_path = os.path.join("credentials", "credentials.json")

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)

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