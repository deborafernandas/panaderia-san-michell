"""
Configuración automática de Gunicorn para Render.
Garantiza que todos los usuarios y peticiones compartan el mismo proceso y base de datos sincronizada.
"""

workers = 1
threads = 4
timeout = 120
