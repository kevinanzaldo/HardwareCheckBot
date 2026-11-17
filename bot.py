# bot.py
import json
import logging
import os
from dotenv import load_dotenv
from google import genai
from pydantic import ValidationError
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
from analisis import analizar_presupuesto
from herramientas import DECLARACIONES, ejecutar_funcion
from prompts import PROMPT_SISTEMA

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

MAX_MENSAJES_HISTORIAL = 20
MAX_VUELTAS_HERRAMIENTAS = 5
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
    entrada = armar_entrada(historial, mensaje)

    for _ in range(MAX_VUELTAS_HERRAMIENTAS):
        interaccion = await cliente_gemini.aio.interactions.create(
            model=GEMINI_MODEL,
            system_instruction=PROMPT_SISTEMA,
            input=entrada,
            tools=DECLARACIONES,
            store=False,
        )

        llamadas = [paso for paso in interaccion.steps if paso.type == "function_call"]
        if not llamadas:
            return interaccion.output_text or "No se pudo generar un diagnóstico en este momento."

        for paso in interaccion.steps:
            entrada.append(paso.model_dump())

        for llamada in llamadas:
            resultado = await ejecutar_funcion(llamada.name, llamada.arguments)
            entrada.append({
                "type": "function_result",
                "call_id": llamada.id,
                "name": llamada.name,
                "result": [{"type": "text", "text": json.dumps(resultado, ensure_ascii=False)}],
            })

    logger.warning("Se alcanzó el máximo de %d vueltas de herramientas", MAX_VUELTAS_HERRAMIENTAS)
    return "No pude completar el diagnóstico técnico con las herramientas. ¿Podés reformular?"

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
        f"¡Hola, {nombre}! Soy RigDoctor v5, tu asistente inteligente de hardware.\n\n"
        "Puedo validar compatibilidades, calcular consumos de fuentes, buscar precios reales en Argentina "
        "y auditar presupuestos completos.\n\n"
        "Escribí /help para ver todos los comandos."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Comandos disponibles:\n\n"
        "/start - Presentación de RigDoctor\n"
        "/help - Esta lista de ayuda\n"
        "/olvidar - Borra la memoria de conversación\n"
        "/analizar <lista de piezas> - Audita un presupuesto de PC de forma estructurada\n"
        "/estadisticas - Muestra el resumen de presupuestos analizados\n\n"
        "También podés preguntarme directamente por precios de hardware o cálculo de watts."
    )

async def olvidar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    borrados = await db.borrar_historial(update.effective_user.id)
    logger.info("Usuario %s borró %d mensajes", update.effective_user.id, borrados)
    await update.message.reply_text("Historial borrado. Banco de pruebas limpio. ¿Qué consulta de hardware tenés?")

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = " ".join(context.args).strip()
    if not texto:
        await update.message.reply_text(
            "Pegá los componentes después del comando. Ejemplo:\n"
            "/analizar Ryzen 5 5600, B550M, 16GB DDR4, RTX 4060"
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        resultado = await analizar_presupuesto(cliente_gemini, GEMINI_MODEL, texto)
    except ValidationError:
        logger.exception("JSON inválido en análisis de presupuesto")
        await update.message.reply_text("No pude estructurar los componentes. Intentá detallarlos un poco más.")
        return
    except Exception as error:
        logger.exception("Error al analizar presupuesto")
        await update.message.reply_text(describir_error(error))
        return

    await db.guardar_presupuesto(update.effective_user.id, texto, resultado)

    await update.message.reply_text(
        f"Auditoría de Presupuesto RigDoctor:\n\n"
        f"CPU: {resultado.cpu}\n"
        f"GPU: {resultado.gpu}\n"
        f"Motherboard: {resultado.motherboard}\n"
        f"Cuello de botella: {resultado.cuello_botella.upper()}\n"
        f"Puntaje de equilibrio: {resultado.puntaje_equilibrio}/10\n"
        f"Diagnóstico: {resultado.observacion_tecnica}"
    )

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    datos = await db.resumen_presupuestos()
    if datos["cantidad"] == 0:
        await update.message.reply_text("Todavía no se auditaron presupuestos. Usá /analizar para probar.")
        return

    conteo = datos["por_cuello"]
    await update.message.reply_text(
        f"Estadísticas del Taller RigDoctor:\n\n"
        f"Presupuestos auditados: {datos['cantidad']}\n"
        f"Equilibrio promedio: {datos['promedio']:.1f}/10\n"
        f"Cuello nulo: {conteo.get('nulo', 0)} | Leve: {conteo.get('leve', 0)} | Severo: {conteo.get('severo', 0)}"
    )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    texto = update.message.text
    logger.info("Mensaje de %s: %s", user_id, texto)

    await update.message.chat.send_action(ChatAction.TYPING)
    historial = await db.obtener_historial(user_id, MAX_MENSAJES_HISTORIAL)

    try:
        respuesta = await consultar_gemini(historial, texto)
    except Exception as error:
        logger.exception("Error al consultar a Gemini")
        await update.message.reply_text(describir_error(error))
        return

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
    app.add_handler(CommandHandler("analizar", analizar))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.add_error_handler(manejar_error)

    logger.info("RigDoctor v5 en línea con modelo %s.", GEMINI_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()