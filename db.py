# db.py
import aiosqlite

RUTA_DB = "hardwarecheckbot.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('user', 'model')),
    texto TEXT NOT NULL,
    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mensajes_usuario ON mensajes (user_id, id);

CREATE TABLE IF NOT EXISTS presupuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    texto_original TEXT NOT NULL,
    cpu TEXT NOT NULL,
    gpu TEXT NOT NULL,
    motherboard TEXT NOT NULL,
    cuello_botella TEXT NOT NULL,
    puntaje_equilibrio INTEGER NOT NULL,
    observacion_tecnica TEXT NOT NULL,
    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

async def inicializar() -> None:
    async with aiosqlite.connect(RUTA_DB) as db:
        await db.executescript(ESQUEMA)
        await db.commit()

async def guardar_intercambio(user_id: int, pregunta: str, respuesta: str) -> None:
    async with aiosqlite.connect(RUTA_DB) as db:
        await db.executemany(
            "INSERT INTO mensajes (user_id, rol, texto) VALUES (?, ?, ?)",
            [
                (user_id, "user", pregunta),
                (user_id, "model", respuesta)
            ]
        )
        await db.commit()

async def obtener_historial(user_id: int, limite: int) -> list[tuple[str, str]]:
    async with aiosqlite.connect(RUTA_DB) as db:
        cursor = await db.execute(
            "SELECT rol, texto FROM mensajes WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limite)
        )
        filas = await cursor.fetchall()
        return list(reversed(filas))

async def borrar_historial(user_id: int) -> int:
    async with aiosqlite.connect(RUTA_DB) as db:
        cursor = await db.execute("DELETE FROM mensajes WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount

async def guardar_presupuesto(user_id: int, texto: str, analisis) -> None:
    async with aiosqlite.connect(RUTA_DB) as db:
        await db.execute(
            """INSERT INTO presupuestos 
               (user_id, texto_original, cpu, gpu, motherboard, cuello_botella, puntaje_equilibrio, observacion_tecnica) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                texto,
                analisis.cpu,
                analisis.gpu,
                analisis.motherboard,
                analisis.cuello_botella,
                analisis.puntaje_equilibrio,
                analisis.observacion_tecnica,
            ),
        )
        await db.commit()

async def resumen_presupuestos() -> dict:
    async with aiosqlite.connect(RUTA_DB) as db:
        cursor = await db.execute("SELECT COUNT(*), AVG(puntaje_equilibrio) FROM presupuestos")
        cantidad, promedio = await cursor.fetchone()
        cursor = await db.execute("SELECT cuello_botella, COUNT(*) FROM presupuestos GROUP BY cuello_botella")
        por_cuello = dict(await cursor.fetchall())
        return {"cantidad": cantidad, "promedio": promedio, "por_cuello": por_cuello}