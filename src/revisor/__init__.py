"""Revisa si una lista de servicios responde por HTTP y entrega un reporte.

El paquete está repartido por responsabilidad, no por tipo de archivo:

- ``servicio``: el vocabulario (Servicio, Estado, Resultado). Sin red ni archivos.
- ``config``: lee y valida la lista de servicios de un archivo TOML.
- ``revisar``: consulta muchos servicios a la vez.
- ``reporte``: convierte resultados en una tabla o en JSON.
- ``cli``: la línea de comandos; arma las piezas y decide el código de salida.
"""
