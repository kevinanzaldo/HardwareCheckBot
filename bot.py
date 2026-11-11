# bot.py
import logging
import os
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
from prompts import PROMPT_SISTEMA

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

MAX_MENSAJES_HISTORIAL = 20
LIMITE_TELEGRAM = 4096

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("hardwarecheckbot")

cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)

def armar_entrada(historial: list[tuple[str, str]], mensaje_nuevo: str) -> list[dict]:
    tipo_de_paso = {"user": "user_input", "model": "model_output"}
    pasos = [
        {"type": tipo_de_paso[rol], "content": [{"type": "text", "text": texto}]}
        for rol, texto in historial
    ]
    pasos.append({"type": "user_input", "content": [{"type": "text", "text": mensaje_nuevo}]})
    return pasos

async def consultar_gemini(historial: list[tuple[str, str]], mensaje: str) -> str:
    interaccion = await cliente_gemini.aio.interactions.create(
        model=GEMINI_MODEL,
        system_instruction=PROMPT_SISTEMA,
        input=armar_entrada(historial, mensaje),
        store=False,
    )
    return interaccion.output_text or "No se pudo generar un diagnóstico en este momento."

def describir_error(error: Exception) -> str:
    codigo = getattr(error, "status_code", None)
    if codigo == 429:
        return "Demasiadas consultas al taller. Por favor reintentá en un minuto."
    if codigo in (401, 403):
        return "Error de credenciales de la API de IA. Avisale al administrador."
    return "Ocurrió una falla técnica al procesar tu consulta. ¿Podés repetirla?"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nombre = update.effective_user.first_name
    await update.message.reply_text(
        f"¡Hola, {nombre}! Soy RigDoctor, tu asistente de diagnóstico y arquitectura de hardware.\n\n"
        "Contame qué componentes tenés o querés armar y te ayudo a validar compatibilidades, consumos y fallas.\n\n"
        "Escribí /help para ver las opciones disponibles."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Comandos disponibles:\n\n"
        "/start - Presentación de RigDoctor\n"
        "/help - Esta lista de ayuda\n"
        "/olvidar - Borra nuestra conversación y empezamos de cero\n\n"
        "Podés preguntarme sobre compatibilidad de sockets, cuellos de botella, cálculo de fuentes o diagnóstico."
    )

async def olvidar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    borrados = await db.borrar_historial(update.effective_user.id)
    logger.info("Usuario %s borró %d mensajes", update.effective_user.id, borrados)
    await update.message.reply_text("Historial borrado. Banco de pruebas limpio. ¿Qué consulta de hardware tenés ahora?")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    texto = update.message.text
    logger.info("Mensaje de %s: %s", user_id, texto)

    await update.message.chat.send_action(ChatAction.TYPING)

    # 1. Recuperar historial
    historial = await db.obtener_historial(user_id, MAX_MENSAJES_HISTORIAL)

    # 2. Consultar a Gemini con memoria
    try:
        respuesta = await consultar_gemini(historial, texto)
    except Exception as error:
        logger.exception("Error al consultar a Gemini")
        await update.message.reply_text(describir_error(error))
        return

    # 3. Guardar en SQLite
    await db.guardar_intercambio(user_id, texto, respuesta)

    for inicio in range(0, len(respuesta), LIMITE_TELEGRAM):
        await update.message.reply_text(respuesta[inicio : inicio + LIMITE_TELEGRAM])

async def manejar_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Excepción general: %s", context.error)

async def al_iniciar(app: Application) -> None:
    await db.inicializar()
    logger.info("Base de datos de RigDoctor lista (%s).", db.RUTA_DB)

def main() -> None:
    faltantes = [n for n, v in [("TELEGRAM_TOKEN", TELEGRAM_TOKEN), ("GEMINI_API_KEY", GEMINI_API_KEY)] if not v]
    if faltantes:
        raise SystemExit(f"Faltan variables en .env: {', '.join(faltantes)}")

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(al_iniciar).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", ayuda))
    app.add_handler(CommandHandler("olvidar", olvidar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.add_error_handler(manejar_error)

    logger.info("RigDoctor v3 en línea con modelo %s.", GEMINI_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()