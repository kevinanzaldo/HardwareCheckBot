# Manual Técnico de Referencia - RigDoctor

## Códigos EZ Debug LED MSI (AM4 y AM5)
LED CPU (Rojo fijo): Indica falla de detección del procesador, pines doblados en socket AM4 o falta de actualización de BIOS para generaciones nuevas (ej: Ryzen 5000 en placas B450).
LED DRAM (Amarillo/Naranja fijo): Falla en entrenamiento de memoria RAM. Verificar que los módulos estén instalados en los slots A2 y B2 (segundo y cuarto desde el socket). En plataformas AM5 el primer entrenamiento puede demorar hasta 3 minutos.
LED VGA (Blanco fijo): Placa de video no detectada o sin alimentación auxiliar PCIe conectada. Si el procesador no tiene gráficos integrados (sufijo F en Intel o modelos Ryzen sin G), el equipo no dará imagen.
LED BOOT (Verde fijo): Sistema operativo no encontrado en las unidades de almacenamiento o modo UEFI/CSM mal configurado en BIOS.

## Q-Codes Post-Error ASUS ROG y TUF
Código 00: No usado / Falla crítica de comunicación entre CPU y motherboard o cable EPS de 8 pines desconectado.
Código 53: Error de inicialización de memoria RAM. Memoria incompatible o frecuencia XMP/EXPO inestable.
Código 55: Memoria RAM no instalada o mal asentada en la ranura DIMM.
Código d6: No se detecta dispositivo de salida de video (GPU mal encajada en slot PCIe x16 o cable DisplayPort/HDMI desconectado).
Código A2: IDE Detect / Fallo de lectura en unidad SATA o NVMe al iniciar el arranque.
Código A9: El equipo ingresó correctamente a la interfaz de configuración de BIOS (estado normal).

## Líneas PCIe y Puertos M.2 Compartidos en Chipsets B550 y B650
En motherboards B550 estándar, el primer slot M.2 (M2_1) y el slot principal PCIe x16 se conectan directo al procesador operando a velocidad PCIe 4.0.
El segundo slot M.2 (M2_2) se gestiona a través del chipset B550 a velocidad PCIe 3.0 x4.
Regla crítica de ancho de banda: En modelos como ASUS TUF Gaming B550-Plus y MSI B550-A Pro, instalar un SSD en el puerto M2_2 deshabilita automáticamente los puertos SATA6G_5 y SATA6G_6 debido a que comparten carriles del chipset.
En chipsets A520 y procesadores Ryzen 5 5500 / Ryzen 7 5700 (arquitectura Cezanne), todas las líneas PCIe están limitadas a generación 3.0.

## Códigos de Pitidos (Beeps) BIOS AMI
1 pitido corto: Arranque normal (POST superado con éxito).
1 pitido largo y 2 cortos: Error de tarjeta gráfica o memoria de video (VRAM).
1 pitido largo y 3 cortos: Falla en memoria RAM principal o falta de detección de GPU en placas modernas.
5 pitidos cortos: Error de procesador (CPU). Revisar temperatura, anclaje del disipador o compatibilidad de microcódigo BIOS.

## Reglas de Instalación Física de Memoria RAM y GPU
Para activar el modo Dual Channel en placas de 4 ranuras, los dos módulos de RAM deben colocarse obligatoriamente en las ranuras A2 y B2 (dejando libre la ranura más cercana al socket del procesador).
Las tarjetas gráficas de más de 2.5 slots de grosor y 280 mm de longitud requieren soporte anti-sag (soporte vertical) para evitar deformación del slot PCIe x16 y microfisuras en las soldaduras de la VRAM.