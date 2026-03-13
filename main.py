from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import os
import json
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are KisanClaim (किसानक्लेम), a friendly AI assistant helping Indian farmers file crop insurance claims under PMFBY (Pradhan Mantri Fasal Bima Yojana).

CRITICAL RULES:
- Detect the language the farmer is speaking/writing in and ALWAYS respond in that SAME language
- If they write in Hindi, respond in Hindi (Devanagari script)
- If they write in Marathi, respond in Marathi
- If they write in Telugu, respond in Telugu script
- If they write in Tamil, respond in Tamil script
- If they write in Kannada, respond in Kannada script
- If they write in Gujarati, respond in Gujarati script
- If they write in English, respond in simple English
- Keep responses under 80 words — clear and voice-friendly
- Be warm, like a helpful neighbor (not a government official)
- Always give ONE clear next step first

KNOWLEDGE BASE:
- PMFBY covers: flood, drought, hailstorm, pest attack, unseasonal rain, landslide
- CRITICAL: Farmer must intimate insurer within 72 HOURS of damage
- Documents needed: Khasra/Khatauni number, land record, bank passbook, Aadhaar
- Patwari does Girdawari (field inspection) — visit them if 72hr window passed
- National Crop Insurance Helpline: 14447 (free, 24/7)
- Check enrollment: pmfby.gov.in or bank passbook

RESPONSE STRUCTURE:
1. First: Is 72-hour window open or closed?
2. Next step: Exact action to take RIGHT NOW
3. Documents to keep ready
4. Helpline 14447 if needed"""


@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    return JSONResponse({"reply": response.content[0].text})


@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice/process",
        language="hi-IN",
        speech_timeout="auto",
        hints="फसल, बीमा, नुकसान, बाढ़, सूखा, ओले, PMFBY"
    )
    gather.say(
        "नमस्ते! मैं किसानक्लेम हूं। आपकी फसल को क्या नुकसान हुआ? कृपया बताएं।",
        language="hi-IN",
        voice="Polly.Aditi"
    )
    response.append(gather)
    return Response(content=str(response), media_type="application/xml")


@app.post("/voice/process")
async def voice_process(request: Request):
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    if not speech_result:
        response = VoiceResponse()
        response.say("कृपया दोबारा बोलें।", language="hi-IN", voice="Polly.Aditi")
        response.redirect("/voice/incoming")
        return Response(content=str(response), media_type="application/xml")

    ai_response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=SYSTEM_PROMPT + "\n\nIMPORTANT: This is a VOICE call. Keep response under 60 words.",
        messages=[{"role": "user", "content": speech_result}]
    )
    reply_text = ai_response.content[0].text
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice/process",
        language="hi-IN",
        speech_timeout="auto"
    )
    gather.say(reply_text, language="hi-IN", voice="Polly.Aditi")
    response.append(gather)
    return Response(content=str(response), media_type="application/xml")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "KisanClaim"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
