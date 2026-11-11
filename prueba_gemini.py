import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
cliente = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

interaccion = cliente.interactions.create(
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    input="Recomendame una placa de video gama media en una sola oración.",
    store=False,
)
print(interaccion.output_text)