from fastapi import FastAPI, WebSocket, Request, Form, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI
from typing import Dict, List
import os
from dotenv import load_dotenv
import uuid
import asyncio
# ---------------- DATABASE SETUP ----------------
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

DATABASE_URL = "sqlite:///./chatbot.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)   # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)
# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# OpenAI client
client = OpenAI(api_key=api_key)

# FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store session-based chat logs
sessions: Dict[str, List[dict]] = {}

# ---------- Chat page ----------
@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    session_id = str(uuid.uuid4())
    
    # Ensure DB session
    db = SessionLocal()
    try:
        # Create a new system prompt (if starting fresh)
        system_msg = ChatMessage(session_id=session_id, role="system", content="You are a helpful AI assistant.")
        db.add(system_msg)
        db.commit()

        # Fetch chat history (should only have the system msg for now)
        chat_history = db.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()

    finally:
        db.close()

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "session_id": session_id, "chat_history": chat_history}
    )

    # Convert DB messages into a list of dicts for frontend
    chat_history = [{"role": msg.role, "content": msg.content} for msg in db_messages]

    db.close()

    # Render template with session_id + chat_history
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "session_id": session_id,
            "chat_history": chat_history
        }
    )

# ---------- WebSocket for real-time chat ----------
@app.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    db = SessionLocal()

    # 👇 Send a greeting immediately on connect
    greeting = "Hello! 👋 I'm your AI assistant. How can I help you today?"
    await websocket.send_text(greeting)

    # Save greeting to DB
    db.add(ChatMessage(session_id=session_id, role="assistant", content=greeting))
    db.commit()

    try:
        while True:
            # --- User message ---
            user_input = await websocket.receive_text()
            db.add(ChatMessage(session_id=session_id, role="user", content=user_input))
            db.commit()

            # --- Build chat history from DB ---
            chat_log = [{"role": "system", "content": "You are a helpful AI assistant."}]
            db_messages = (
                db.query(ChatMessage)
                .filter_by(session_id=session_id)
                .order_by(ChatMessage.timestamp)
                .all()
            )
            for msg in db_messages:
                chat_log.append({"role": msg.role, "content": msg.content})

            # --- Call OpenAI API ---
            response = client.chat.completions.create(
                model="gpt-4",
                messages=chat_log,
                temperature=0.6
            )

            ai_response = response.choices[0].message.content

            # --- Send + Save assistant response ---
            await websocket.send_text(ai_response)
            db.add(ChatMessage(session_id=session_id, role="assistant", content=ai_response))
            db.commit()

    except WebSocketDisconnect:
        print(f"Session {session_id} disconnected")
    finally:
        db.close()


@app.post("/image", response_class=HTMLResponse)
async def create_image(request: Request, user_input: str = Form(...)):
    # Call OpenAI Images API
    response = client.images.generate(
        model="gpt-image-1",   # Required model name
        prompt=user_input,
        size="512x512",        # You can use "256x256", "512x512", "1024x1024"
        n=1
    )

    # Extract the URL of the generated image
    image_url = response.data[0].url

    return templates.TemplateResponse(
        "image.html",
        {"request": request, "image_url": image_url, "user_input": user_input}
    )
