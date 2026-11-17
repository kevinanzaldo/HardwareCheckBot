# analisis.py
from typing import Literal
from pydantic import BaseModel, Field

class AnalisisPresupuesto(BaseModel):
    """Estructura fija para el parsing y diagnóstico de presupuestos de PC."""
    cpu: str = Field(description="Modelo de procesador detectado o 'No especificado'.")
    gpu: str = Field(description="Modelo de placa de video detectado o 'No especificado'.")
    motherboard: str = Field(description="Modelo/chipset de motherboard detectado o 'No especificado'.")
    cuello_botella: Literal["nulo", "leve", "severo", "indeterminado"] = Field(
        description="Nivel de cuello de botella estimado entre CPU y GPU."
    )
    puntaje_equilibrio: int = Field(
        ge=1, le=10,
        description="Puntaje de coherencia y equilibrio técnico del armado, de 1 (muy malo) a 10 (óptimo)."
    )
    observacion_tecnica: str = Field(
        description="Diagnóstico técnico en una oración breve y directa."
    )

PROMPT_ANALISIS = """
Sos un parser técnico de arquitectura de PC. Extraé los componentes del presupuesto o listado enviado por el usuario y evaluá su equilibrio técnico.
Respondé únicamente siguiendo el esquema JSON solicitado, en español.
Si faltan componentes clave para evaluar cuello de botella (como CPU o GPU), marcá cuello_botella como 'indeterminado'.
""".strip()

async def analizar_presupuesto(cliente, modelo: str, texto: str) -> AnalisisPresupuesto:
    interaccion = await cliente.aio.interactions.create(
        model=modelo,
        system_instruction=PROMPT_ANALISIS,
        input=texto,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": AnalisisPresupuesto.model_json_schema(),
        },
        store=False,
    )
    return AnalisisPresupuesto.model_validate_json(interaccion.output_text)