# rag.py
import json
import logging
import numpy as np
from google.genai import types

logger = logging.getLogger("hardwarecheckbot")

RUTA_GUIA = "guia/manual_hardware.md"
RUTA_INDICE = "guia/indice.json"
MODELO_EMBEDDINGS = "gemini-embedding-2"
DIMENSION = 768
UMBRAL_SIMILITUD = 0.35

_cliente = None
_fragmentos = []
_matriz = None

def leer_fragmentos(ruta: str = RUTA_GUIA) -> list[dict]:
    with open(ruta, encoding="utf-8") as archivo:
        contenido = archivo.read()
    fragmentos = []
    for seccion in contenido.split("\n## ")[1:]:
        titulo, _, cuerpo = seccion.partition("\n")
        fragmentos.append({"titulo": titulo.strip(), "texto": cuerpo.strip()})
    return fragmentos

async def obtener_embedding(cliente, texto: str) -> list[float]:
    respuesta = await cliente.aio.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=texto,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSION),
    )
    return respuesta.embeddings[0].values

async def indexar(cliente) -> int:
    fragmentos = leer_fragmentos()
    for fragmento in fragmentos:
        texto = f"title: {fragmento['titulo']} | text: {fragmento['texto']}"
        fragmento["vector"] = await obtener_embedding(cliente, texto)
        logger.info("Indexado: %s", fragmento["titulo"])
    with open(RUTA_INDICE, "w", encoding="utf-8") as archivo:
        json.dump(fragmentos, archivo, ensure_ascii=False)
    return len(fragmentos)

def _normalizar_filas(matriz: np.ndarray) -> np.ndarray:
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    return matriz / normas

def inicializar(cliente) -> None:
    global _cliente, _fragmentos, _matriz
    _cliente = cliente
    try:
        with open(RUTA_INDICE, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError:
        logger.warning("No existe %s: ejecutá python indexar_guia.py", RUTA_INDICE)
        return
    _fragmentos = [{"titulo": d["titulo"], "texto": d["texto"]} for d in datos]
    _matriz = _normalizar_filas(np.array([d["vector"] for d in datos]))
    logger.info("Manual técnico cargado: %d secciones.", len(_fragmentos))

async def buscar(consulta: str, cantidad: int = 3) -> list[dict]:
    if _matriz is None:
        raise RuntimeError("El manual técnico no está indexado")
    vector = np.array(await obtener_embedding(_cliente, f"task: search result | query: {consulta}"))
    vector = vector / np.linalg.norm(vector)
    similitudes = _matriz @ vector
    mejores = np.argsort(similitudes)[::-1][:cantidad]
    logger.info(
        "Búsqueda RAG '%s': %s",
        consulta,
        [(_fragmentos[i]["titulo"], round(float(similitudes[i]), 2)) for i in mejores],
    )
    return [
        {**_fragmentos[i], "similitud": round(float(similitudes[i]), 3)}
        for i in mejores
        if similitudes[i] >= UMBRAL_SIMILITUD
    ]