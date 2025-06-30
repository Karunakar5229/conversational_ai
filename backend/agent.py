import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.tools import tool
from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from dateparser.search import search_dates
from backend.calendar_utils import get_available_slots, book_event

load_dotenv()
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)

class AgentState(dict):
    user_input: str
    response: str

def parse_datetime_from_text(text: str) -> datetime | None:
    results = search_dates(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now()
        }
    )
    if results:
        for _, dt in results:
            if dt > datetime.now():
                if dt.hour == 0 and dt.minute == 0:
                    dt = dt.replace(hour=10, minute=0)
                print(f"🧠 Parsed datetime: {dt}")
                return dt
    return None

@tool
def check_availability_tool(text: str) -> str:
    """Check available time slots in calendar based on user input."""
    parsed_time = parse_datetime_from_text(text)
    if not parsed_time:
        return "❌ I couldn't understand the time. Try something like 'this Friday afternoon'."

    start = parsed_time
    end = start + timedelta(hours=3)
    if start < datetime.now():
        return "⚠ That time is in the past. Please choose a future time."

    slots = get_available_slots(start, end)
    if not slots:
        return "😕 No available slots found."

    readable = ", ".join(s.strftime("%I:%M %p") for s in slots if 7 <= s.hour < 22)
    return "🕒 Here are your free slots: " + readable if readable else "😕 Only midnight/early morning slots found."

@tool
def book_meeting_tool(text: str) -> str:
    """Book a 30-minute meeting via Google Calendar based on user input."""
    parsed_time = parse_datetime_from_text(text)
    if not parsed_time:
        return "❌ Could not understand when to book. Try something like 'next Monday at 2 PM'."

    start = parsed_time
    end = start + timedelta(hours=3)
    if start < datetime.now():
        return "⚠ Cannot book meetings in the past."

    slots = get_available_slots(start, end)
    working_slots = [s for s in slots if 7 <= s.hour < 22]
    if not working_slots:
        return "😕 No available slots found during working hours."

    # Exact match
    exact_match = next((s for s in working_slots if s.hour == parsed_time.hour and abs(s.minute - parsed_time.minute) <= 10), None)

    if exact_match:
        slot_start = exact_match
        slot_end = slot_start + timedelta(minutes=30)
        link = book_event(slot_start, slot_end, text)
        return f"✅ Great! Your meeting is set for {slot_start.strftime('%A %I:%M %p')}. [View Event]({link})" if link else "❌ Booking failed."
    else:
        suggestions = ", ".join(s.strftime("%I:%M %p") for s in working_slots[:5])
        return f"❌ No slot available exactly at {parsed_time.strftime('%I:%M %p')}. Try one of these nearby: {suggestions}"

def fallback_small_talk(user_input: str) -> str:
    user_input = user_input.lower()
    greetings = ["hi", "hello", "hey"]
    thanks = ["thanks", "thank you"]

    if any(g in user_input for g in greetings):
        return "👋 Hello! I can help you manage and book meetings. Just ask!"
    elif any(t in user_input for t in thanks):
        return "😊 You're very welcome. Happy to help!"
    elif "how are you" in user_input:
        return "I'm great, thanks for asking! How can I assist with your meetings today?"
    else:
        return "🤖 I'm a meeting assistant. You can ask me to 'book a meeting tomorrow at 10 AM' or 'check availability this Friday'."

def agent_logic(state: AgentState):
    user_input = state["user_input"].lower()
    keywords = {
        "book": ["book", "schedule", "set meeting", "arrange", "reserve"],
        "check": ["available", "free", "slots", "vacant", "availability"],
    }

    try:
        if any(word in user_input for word in keywords["book"]):
            result = book_meeting_tool.invoke(user_input)
        elif any(word in user_input for word in keywords["check"]):
            result = check_availability_tool.invoke(user_input)
        else:
            print("💬 Fallback to GPT response")
            try:
                response = llm.invoke(user_input)
                result = response.content if hasattr(response, "content") else str(response)
            except Exception:
                result = fallback_small_talk(user_input)

        return {
            "user_input": state["user_input"],
            "response": result
        }
    except Exception as e:
        return {"user_input": state["user_input"], "response": f"❌ Error: {e}"}

def get_graph():
    builder = StateGraph(AgentState)
    builder.add_node("agent", RunnableLambda(agent_logic))
    builder.set_entry_point("agent")
    builder.set_finish_point("agent")
    return builder.compile()

graph = get_graph()

def run_agent(message: str) -> str:
    result = graph.invoke({"user_input": message})
    return result["response"]