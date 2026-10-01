# Luree-AI-agent

Open `/assistant` for the Arabic chat interface and animated agent face.

- Enable **الصوت** to read new replies using your device's installed voices.
- **قراءة آخر رد** replays the latest reply; **إيقاف الصوت** cancels speech.
- **إملاء رسالة** requests microphone permission and fills the message box. Review the text and press Send.
- Dictation requires HTTPS and browser speech recognition support. If unavailable, use keyboard dictation or type. Arabic playback quality depends on installed voices. Browser dictation may use the browser provider's speech service.
- No extra OpenAI voice API calls are made by these controls.

Run `gunicorn app:app --bind 0.0.0.0:8080` with the existing environment variables.
