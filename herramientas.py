# herramientas.py
import logging
import unicodedata
import httpx
import rag

logger = logging.getLogger("hardwarecheckbot")
TIEMPO_ESPERA = 5

TIPOS_DOLAR = ["oficial", "blue", "tarjeta", "bolsa"]

def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower().strip()


# --- 1. Funciones ---

async def obtener_cotizacion_dolar(tipo: str = "blue") -> dict:
    """Consulta la cotización actual del dólar en Argentina vía DolarAPI."""
    tipo = _normalizar(tipo)
    if tipo not in TIPOS_DOLAR:
        return {"error": f"Tipo de cotización desconocido: {tipo}", "tipos_disponibles": TIPOS_DOLAR}

    url = f"https://dolarapi.com/v1/dolares/{tipo}"
    try:
        async with httpx.AsyncClient(timeout=TIEMPO_ESPERA) as cliente_http:
            respuesta = await cliente_http.get(url)
            respuesta.raise_for_status()
            datos = respuesta.json()

        return {
            "tipo": datos.get("nombre", tipo),
            "compra_ars": datos.get("compra"),
            "venta_ars": datos.get("venta"),
            "actualizado": datos.get("fechaActualizacion"),
        }
    except Exception as error:
        logger.exception("Error consultando DolarAPI")
        return {"error": f"No se pudo obtener la cotización: {type(error).__name__}"}


async def calcular_consumo_psu(tdp_cpu_watts: int, tdp_gpu_watts: int, overclock: bool = False) -> dict:
    """Calcula el consumo total del sistema y recomienda la fuente (PSU) adecuada."""
    if tdp_cpu_watts < 15 or tdp_gpu_watts < 0:
        return {"error": "Valores de TDP inválidos. Verificá los watts de CPU y GPU."}

    consumo_base_resto = 75
    consumo_total_nominal = tdp_cpu_watts + tdp_gpu_watts + consumo_base_resto

    factor_picos = 1.35 if overclock else 1.25
    consumo_pico_estimado = round(consumo_total_nominal * factor_picos)
    potencia_ideal = round(consumo_pico_estimado / 0.80)

    estandares_psu = [450, 500, 550, 600, 650, 750, 850, 1000, 1200]
    psu_recomendada = next((w for w in estandares_psu if w >= potencia_ideal), 1200)
    certificacion = "80 Plus Gold" if psu_recomendada >= 750 else "80 Plus Bronze"

    return {
        "consumo_nominal_watts": consumo_total_nominal,
        "consumo_pico_transitorio_watts": consumo_pico_estimado,
        "psu_recomendada_watts": psu_recomendada,
        "certificacion_sugerida": certificacion,
    }


async def buscar_en_manual(consulta: str) -> dict:
    """Busca información técnica en el manual de referencia de RigDoctor (RAG)."""
    resultados = await rag.buscar(consulta)
    if not resultados:
        return {
            "resultados": [],
            "aviso": "El manual técnico de RigDoctor no contiene información sobre esta consulta.",
        }
    return {"resultados": resultados}


# --- 2. Declaraciones JSON Schema para Gemini ---

DECLARACIONES = [
    {
        "type": "function",
        "name": "obtener_cotizacion_dolar",
        "description": (
            "Obtiene la cotización actual del dólar estadounidense en pesos argentinos (compra y venta). "
            "Usala siempre que el usuario pregunte cuánto está el dólar o pida convertir a pesos argentinos "
            "el precio en dólares de un componente de hardware (ej: cuánto salen 350 USD de una GPU en pesos)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": TIPOS_DOLAR,
                    "description": "Tipo de cambio: 'blue' para mercado informal/efectivo, 'bolsa' para MEP, 'tarjeta' para compras en el exterior, 'oficial' para referencia bancaria. Por defecto 'blue'.",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "calcular_consumo_psu",
        "description": (
            "Calcula el consumo eléctrico estimado del sistema (incluyendo picos transitorios) y "
            "determina la potencia en Watts y certificación recomendada de la fuente de alimentación (PSU). "
            "Usala cuando el usuario pregunte qué fuente necesita o si su fuente actual alcanza para un combo de CPU y GPU."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tdp_cpu_watts": {
                    "type": "integer",
                    "description": "Consumo TDP nominal del procesador en Watts (ej: 65 para Ryzen 5 5600X, 125 para i5-13600K).",
                },
                "tdp_gpu_watts": {
                    "type": "integer",
                    "description": "Consumo TBP/TDP de la tarjeta gráfica en Watts (ej: 230 para RX 6700 XT, 0 si usa gráficos integrados).",
                },
                "overclock": {
                    "type": "boolean",
                    "description": "True si el usuario planea hacer overclocking, False por defecto.",
                },
            },
            "required": ["tdp_cpu_watts", "tdp_gpu_watts"],
        },
    },
    {
        "type": "function",
        "name": "buscar_en_manual",
        "description": (
            "Busca en el manual técnico de referencia de RigDoctor información sobre códigos de error "
            "(EZ Debug LED, Q-Codes ASUS, pitidos BIOS), conflictos entre puertos M.2 y SATA, "
            "distribución de líneas PCIe y reglas de instalación de RAM/GPU. "
            "Usala SIEMPRE ante consultas de diagnóstico de LEDs, códigos POST o conflictos de puertos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Palabras clave de la consulta técnica, por ejemplo: 'Q-Code 55 ASUS' o 'puertos SATA deshabilitados M2_2 B550'.",
                },
            },
            "required": ["consulta"],
        },
    },
]

# --- 3. Despachador ---

FUNCIONES = {
    "obtener_cotizacion_dolar": obtener_cotizacion_dolar,
    "calcular_consumo_psu": calcular_consumo_psu,
    "buscar_en_manual": buscar_en_manual,
}

async def ejecutar_funcion(nombre: str, argumentos: dict) -> dict:
    logger.info("El modelo pidió %s(%s)", nombre, argumentos)
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return {"error": f"Función desconocida: {nombre}"}
    try:
        return await funcion(**argumentos)
    except Exception as error:
        logger.exception("Falló la herramienta %s", nombre)
        return {"error": f"No se pudo ejecutar la herramienta: {type(error).__name__}"}