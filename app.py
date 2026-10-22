"""
Sistema de Gestión de Proveedores, Pedidos y Facturación
Negocio: Panadería San Michell
Autora: Débora
Tecnologías: Python + Flask + SQLite3
"""

import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
# Clave secreta necesaria en Flask para mostrar mensajes alerta (flash messages) en la interfaz
app.secret_key = "san_michell_clave_secreta_universidad"

DB_NAME = "san_michell.db"
LOCAL_BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "san_michell_respaldo.json")
CLOUD_BACKUP_URL = os.environ.get(
    "SAN_MICHELL_CLOUD_URL",
    "https://textdb.dev/api/data/panaderia-san-michell-db-v1-debora"
)
_ULTIMA_CONSULTA_NUBE = 0.0


@app.after_request
def add_no_cache_headers(response):
    """
    Evita que el navegador guarde en caché páginas antiguas al agregar, modificar o eliminar proveedores/facturas.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_db_connection():
    """
    Crea y retorna una conexión a la base de datos SQLite.
    Usamos sqlite3.Row para poder acceder a las columnas por su nombre (ej: factura['monto'])
    como si fueran diccionarios, lo que hace el código mucho más legible.
    """
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def obtener_version_datos(conn):
    row = conn.execute("SELECT valor FROM meta_estado WHERE clave = 'version_datos'").fetchone()
    try:
        return int(row["valor"]) if row else 0
    except (ValueError, TypeError):
        return 0


def actualizar_version_datos(conn):
    actual = obtener_version_datos(conn)
    nuevo_ts = max(actual + 1, int(datetime.now().timestamp() * 1000))
    conn.execute(
        "INSERT OR REPLACE INTO meta_estado (clave, valor) VALUES ('version_datos', ?)",
        (str(nuevo_ts),)
    )
    return nuevo_ts


def exportar_estado_completo(conn):
    dists = [dict(r) for r in conn.execute("SELECT * FROM distribuidores ORDER BY id ASC").fetchall()]
    facts = [dict(r) for r in conn.execute("SELECT * FROM facturas ORDER BY id ASC").fetchall()]
    return {
        "version_datos": obtener_version_datos(conn),
        "distribuidores": dists,
        "facturas": facts,
    }


def aplicar_respaldo_en_db(conn, payload):
    """
    Restaura la base de datos desde el respaldo del navegador cuando el contenedor gratuito de Render
    se reinicia por inactividad o despliegue, evitando que se borren los proveedores o facturas ingresadas.
    """
    if not isinstance(payload, dict):
        return False
    version_cliente = int(payload.get("version_datos", 0) or 0)
    version_servidor = obtener_version_datos(conn)
    if version_cliente <= version_servidor:
        return False

    dists = payload.get("distribuidores")
    facts = payload.get("facturas")
    if not isinstance(dists, list) or not isinstance(facts, list):
        return False

    cursor = conn.cursor()
    cursor.execute("DELETE FROM facturas")
    cursor.execute("DELETE FROM distribuidores")

    for d in dists:
        cursor.execute("""
            INSERT INTO distribuidores (id, nombre, rut_empresa, telefono, rubro_insumo, fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            d.get("id"),
            d.get("nombre", ""),
            d.get("rut_empresa", ""),
            d.get("telefono", ""),
            d.get("rubro_insumo", ""),
            d.get("fecha_registro", datetime.now().strftime("%Y-%m-%d")),
        ))

    for f in facts:
        cursor.execute("""
            INSERT INTO facturas (id, distribuidor_id, numero_factura, fecha, tipo_frecuencia, detalle_pedido, monto, medio_pago)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f.get("id"),
            f.get("distribuidor_id"),
            f.get("numero_factura", ""),
            f.get("fecha", ""),
            f.get("tipo_frecuencia", "Diaria"),
            f.get("detalle_pedido", ""),
            int(f.get("monto", 0) or 0),
            f.get("medio_pago", "Efectivo"),
        ))

    cursor.execute(
        "INSERT OR REPLACE INTO meta_estado (clave, valor) VALUES ('version_datos', ?)",
        (str(version_cliente),)
    )
    cursor.execute(
        "INSERT OR REPLACE INTO meta_estado (clave, valor) VALUES ('semilla_cargada', '1')"
    )
    conn.commit()
    return True


def cargar_respaldo_nube():
    """
    Descarga el respaldo persistente desde la nube para que los proveedores y facturas
    se mantengan guardados aunque Render reinicie o formatee el contenedor gratuito,
    y para que se sincronicen automáticamente entre distintos computadores o celulares.
    """
    try:
        req = urllib.request.Request(
            CLOUD_BACKUP_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8").strip()
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict) and "version_datos" in data:
                    return data
    except Exception as e:
        print(f"Aviso: No se pudo leer respaldo en la nube: {e}")

    try:
        if os.path.exists(LOCAL_BACKUP_FILE):
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "version_datos" in data:
                    return data
    except Exception:
        pass
    return None


def guardar_respaldo_nube(conn):
    """
    Guarda inmediatamente el estado actual de proveedores y facturas en la nube
    cada vez que se ingresa, modifica o elimina un registro.
    """
    global _ULTIMA_CONSULTA_NUBE
    estado = exportar_estado_completo(conn)
    raw_json = json.dumps(estado, ensure_ascii=True)

    try:
        with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(raw_json)
    except Exception:
        pass

    try:
        req = urllib.request.Request(
            CLOUD_BACKUP_URL,
            data=raw_json.encode("ascii"),
            headers={
                "Content-Type": "text/plain",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp.read()
        _ULTIMA_CONSULTA_NUBE = time.time()
        return True
    except Exception as e:
        print(f"Aviso: No se pudo guardar respaldo en la nube: {e}")
        return False


def sincronizar_desde_nube_si_necesario(conn, forzar=False):
    """
    Verifica si existe una versión más reciente de los proveedores y facturas en la nube
    y la restaura en la base de datos SQLite local antes de mostrar o modificar datos.
    """
    global _ULTIMA_CONSULTA_NUBE
    ahora = time.time()
    version_local = obtener_version_datos(conn)
    if not forzar and version_local > 0 and (ahora - _ULTIMA_CONSULTA_NUBE) < 3.0:
        return False

    _ULTIMA_CONSULTA_NUBE = ahora
    respaldo_nube = cargar_respaldo_nube()
    if respaldo_nube:
        return aplicar_respaldo_en_db(conn, respaldo_nube)
    return False


def restaurar_desde_formulario_si_necesario(conn):
    sincronizar_desde_nube_si_necesario(conn, forzar=True)
    respaldo_raw = request.form.get("respaldo_cliente", "").strip()
    if not respaldo_raw:
        return
    try:
        payload = json.loads(respaldo_raw)
        if aplicar_respaldo_en_db(conn, payload):
            guardar_respaldo_nube(conn)
    except Exception:
        pass


def init_db():
    """
    Inicializa las tablas en la base de datos si aún no existen.
    Contiene dos tablas principales relacionadas entre sí (Clave Foránea / Foreign Key):
    1. distribuidores: Almacena los proveedores de la panadería.
    2. facturas: Almacena cada factura/pedido asociado a un distribuidor.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla 0: Control de estado y versión para persistencia
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta_estado (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)

    # Tabla 1: Distribuidores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS distribuidores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            rut_empresa TEXT,
            telefono TEXT,
            rubro_insumo TEXT NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    """)

    # Tabla 2: Facturas y Pedidos
    # Incluye el tipo_frecuencia ('Diaria', 'Semanal', 'Mensual') y medio_pago ('Efectivo', 'Cheque', 'Transferencia')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distribuidor_id INTEGER NOT NULL,
            numero_factura TEXT NOT NULL,
            fecha TEXT NOT NULL,
            tipo_frecuencia TEXT NOT NULL CHECK(tipo_frecuencia IN ('Diaria', 'Semanal', 'Mensual')),
            detalle_pedido TEXT NOT NULL,
            monto INTEGER NOT NULL,
            medio_pago TEXT NOT NULL CHECK(medio_pago IN ('Efectivo', 'Cheque', 'Transferencia')),
            FOREIGN KEY (distribuidor_id) REFERENCES distribuidores (id) ON DELETE CASCADE
        )
    """)
    conn.commit()

    # Primero intentamos restaurar desde el respaldo en la nube para no reiniciar a los datos de fábrica
    sincronizar_desde_nube_si_necesario(conn, forzar=True)

    # Insertar semilla solo una vez si no existe ningún respaldo previo en la nube ni en la base local
    semilla = cursor.execute("SELECT valor FROM meta_estado WHERE clave = 'semilla_cargada'").fetchone()
    if not semilla:
        cursor.execute("SELECT COUNT(*) as total FROM distribuidores")
        if cursor.fetchone()["total"] == 0:
            hoy_mes = datetime.now().strftime("%Y-%m")
            distribuidores_iniciales = [
                ("Molinos del Sur S.A.", "76.123.456-8", "+56 9 8765 4321", "Harinas y Levaduras", f"{hoy_mes}-01"),
                ("Lácteos y Mantecas Valle Verde", "77.987.654-3", "+56 9 6543 2109", "Lácteos, Huevos y Manteca", f"{hoy_mes}-01"),
                ("Distribuidora Dulce Pan", "78.444.555-K", "+56 9 5555 1234", "Azúcar, Chocolate y Repostería", f"{hoy_mes}-02"),
            ]
            cursor.executemany("""
                INSERT INTO distribuidores (nombre, rut_empresa, telefono, rubro_insumo, fecha_registro)
                VALUES (?, ?, ?, ?, ?)
            """, distribuidores_iniciales)

            facturas_iniciales = [
                (1, "F-10421", f"{hoy_mes}-03", "Diaria", "10 sacos de harina flor 25kg + 5kg levadura fresca", 245000, "Transferencia"),
                (1, "F-10489", f"{hoy_mes}-10", "Semanal", "25 sacos de harina panadera + mejorador de masa", 580000, "Cheque"),
                (2, "F-8832", f"{hoy_mes}-05", "Diaria", "30 bandejas de huevos + 15kg manteca", 165000, "Efectivo"),
                (2, "F-8910", f"{hoy_mes}-15", "Semanal", "50L leche entera + 20kg queso laminado + crema pastelera", 320000, "Transferencia"),
                (3, "F-3011", f"{hoy_mes}-20", "Mensual", "Pedido mensual insumos pastelería: cobertura chocolate, azúcar flor y esencias", 490000, "Cheque"),
            ]
            cursor.executemany("""
                INSERT INTO facturas (distribuidor_id, numero_factura, fecha, tipo_frecuencia, detalle_pedido, monto, medio_pago)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, facturas_iniciales)

        cursor.execute("INSERT OR REPLACE INTO meta_estado (clave, valor) VALUES ('semilla_cargada', '1')")
        cursor.execute("INSERT OR IGNORE INTO meta_estado (clave, valor) VALUES ('version_datos', '1')")

    conn.commit()
    conn.close()


@app.route("/")
def index():
    """
    Ruta principal (Dashboard).
    Muestra los formularios por pestañas (Diaria, Semanal, Mensual), la gestión de distribuidores,
    las tablas de facturas y el comparador de fin de mes por distribuidor.
    """
    conn = get_db_connection()
    sincronizar_desde_nube_si_necesario(conn)

    # Mes seleccionado en el filtro para el cierre/comparación de fin de mes (por defecto el mes actual YYYY-MM)
    mes_actual = datetime.now().strftime("%Y-%m")
    mes_filtro = request.args.get("mes", mes_actual)
    distribuidor_filtro = request.args.get("distribuidor_id", "todos")

    # 1. Obtener lista completa de distribuidores
    distribuidores = conn.execute("SELECT * FROM distribuidores ORDER BY nombre ASC").fetchall()

    # 2. Construir consulta de facturas filtradas por el mes seleccionado
    query_facturas = """
        SELECT f.*, d.nombre AS distribuidor_nombre, d.rubro_insumo
        FROM facturas f
        JOIN distribuidores d ON f.distribuidor_id = d.id
        WHERE strftime('%Y-%m', f.fecha) = ?
    """
    params = [mes_filtro]

    if distribuidor_filtro != "todos" and distribuidor_filtro.isdigit():
        query_facturas += " AND f.distribuidor_id = ?"
        params.append(int(distribuidor_filtro))

    query_facturas += " ORDER BY f.fecha DESC, f.id DESC"
    facturas = conn.execute(query_facturas, params).fetchall()

    # 3. Separar las facturas según su clasificación manual: Diaria, Semanal, Mensual
    facturas_diarias = [f for f in facturas if f["tipo_frecuencia"] == "Diaria"]
    facturas_semanales = [f for f in facturas if f["tipo_frecuencia"] == "Semanal"]
    facturas_mensuales = [f for f in facturas if f["tipo_frecuencia"] == "Mensual"]

    # 4. Calcular totales para comparar gastos (Diarios vs Semanales vs Mensuales)
    totales_frecuencia = {
        "Diaria": sum(f["monto"] for f in facturas_diarias),
        "Semanal": sum(f["monto"] for f in facturas_semanales),
        "Mensual": sum(f["monto"] for f in facturas_mensuales),
    }
    total_general_mes = sum(totales_frecuencia.values())

    # 5. Calcular totales por medio de pago (Efectivo, Cheque, Transferencia)
    totales_pago = {
        "Efectivo": sum(f["monto"] for f in facturas if f["medio_pago"] == "Efectivo"),
        "Cheque": sum(f["monto"] for f in facturas if f["medio_pago"] == "Cheque"),
        "Transferencia": sum(f["monto"] for f in facturas if f["medio_pago"] == "Transferencia"),
    }

    # 6. Comparativa de fin de mes por Distribuidor (Gastos y Pedidos acumulados en el mes)
    # Usamos GROUP BY en SQL para agrupar todas las facturas de cada distribuidor en el mes elegido
    comparativa_distribuidores = conn.execute("""
        SELECT 
            d.id,
            d.nombre,
            d.rubro_insumo,
            COUNT(f.id) AS cantidad_pedidos,
            COALESCE(SUM(f.monto), 0) AS total_gastado,
            COALESCE(SUM(CASE WHEN f.tipo_frecuencia = 'Diaria' THEN f.monto ELSE 0 END), 0) AS gasto_diario,
            COALESCE(SUM(CASE WHEN f.tipo_frecuencia = 'Semanal' THEN f.monto ELSE 0 END), 0) AS gasto_semanal,
            COALESCE(SUM(CASE WHEN f.tipo_frecuencia = 'Mensual' THEN f.monto ELSE 0 END), 0) AS gasto_mensual,
            COALESCE(SUM(CASE WHEN f.medio_pago = 'Efectivo' THEN f.monto ELSE 0 END), 0) AS pago_efectivo,
            COALESCE(SUM(CASE WHEN f.medio_pago = 'Cheque' THEN f.monto ELSE 0 END), 0) AS pago_cheque,
            COALESCE(SUM(CASE WHEN f.medio_pago = 'Transferencia' THEN f.monto ELSE 0 END), 0) AS pago_transferencia,
            GROUP_CONCAT(f.numero_factura || ' (' || f.detalle_pedido || ')', ' | ') AS resumen_pedidos
        FROM distribuidores d
        LEFT JOIN facturas f ON d.id = f.distribuidor_id AND strftime('%Y-%m', f.fecha) = ?
        GROUP BY d.id
        ORDER BY total_gastado DESC
    """, (mes_filtro,)).fetchall()

    estado_respaldo = exportar_estado_completo(conn)
    conn.close()

    return render_template(
        "index.html",
        distribuidores=distribuidores,
        facturas=facturas,
        facturas_diarias=facturas_diarias,
        facturas_semanales=facturas_semanales,
        facturas_mensuales=facturas_mensuales,
        totales_frecuencia=totales_frecuencia,
        total_general_mes=total_general_mes,
        totales_pago=totales_pago,
        comparativa_distribuidores=comparativa_distribuidores,
        mes_filtro=mes_filtro,
        distribuidor_filtro=distribuidor_filtro,
        fecha_hoy=datetime.now().strftime("%Y-%m-%d"),
        estado_respaldo=estado_respaldo
    )


@app.route("/api/sincronizar", methods=["POST"])
def api_sincronizar():
    """
    Sincroniza automáticamente el respaldo del navegador y la nube con el servidor si el contenedor gratuito
    de Render se reinició tras un período de inactividad o despliegue.
    """
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    sincronizar_desde_nube_si_necesario(conn, forzar=True)
    restaurado = aplicar_respaldo_en_db(conn, payload)
    if restaurado:
        guardar_respaldo_nube(conn)
    estado = exportar_estado_completo(conn)
    conn.close()
    return jsonify({"ok": True, "restaurado": restaurado, "estado": estado})


@app.route("/distribuidor/nuevo", methods=["POST"])
def nuevo_distribuidor():
    """
    Recibe los datos del formulario para registrar un nuevo distribuidor en la base de datos.
    """
    nombre = request.form.get("nombre", "").strip()
    rut_empresa = request.form.get("rut_empresa", "").strip()
    telefono = request.form.get("telefono", "").strip()
    rubro_insumo = request.form.get("rubro_insumo", "").strip()
    fecha_registro = datetime.now().strftime("%Y-%m-%d")

    if not nombre or not rubro_insumo:
        flash("Por favor completa el nombre del distribuidor y su rubro de insumos.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("""
        INSERT INTO distribuidores (nombre, rut_empresa, telefono, rubro_insumo, fecha_registro)
        VALUES (?, ?, ?, ?, ?)
    """, (nombre, rut_empresa, telefono, rubro_insumo, fecha_registro))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    flash(f"Distribuidor '{nombre}' agregado correctamente a Panadería San Michell.", "success")
    return redirect(url_for("index"))


@app.route("/factura/nueva", methods=["POST"])
def nueva_factura():
    """
    Recibe los datos de una factura (Diaria, Semanal o Mensual), junto con el número de factura,
    detalle del pedido, monto a cancelar y medio de pago (Efectivo, Cheque o Transferencia).
    """
    distribuidor_id = request.form.get("distribuidor_id")
    numero_factura = request.form.get("numero_factura", "").strip()
    fecha = request.form.get("fecha", "").strip()
    tipo_frecuencia = request.form.get("tipo_frecuencia", "").strip()
    detalle_pedido = request.form.get("detalle_pedido", "").strip()
    monto = request.form.get("monto", "0").strip()
    medio_pago = request.form.get("medio_pago", "").strip()

    if not (distribuidor_id and numero_factura and fecha and tipo_frecuencia and detalle_pedido and monto and medio_pago):
        flash("Todos los campos de la factura y pedido son obligatorios.", "danger")
        return redirect(url_for("index"))

    try:
        monto_entero = int(float(monto))
    except ValueError:
        flash("El monto a cancelar debe ser un valor numérico válido.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("""
        INSERT INTO facturas (distribuidor_id, numero_factura, fecha, tipo_frecuencia, detalle_pedido, monto, medio_pago)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (int(distribuidor_id), numero_factura, fecha, tipo_frecuencia, detalle_pedido, monto_entero, medio_pago))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    # Redirigir manteniendo el mes de la factura recién ingresada para que el usuario la vea de inmediato
    mes_factura = fecha[:7]
    flash(f"Factura N° {numero_factura} ({tipo_frecuencia}) registrada exitosamente por ${monto_entero:,}.", "success")
    return redirect(url_for("index", mes=mes_factura))


@app.route("/factura/editar/<int:factura_id>", methods=["POST"])
def editar_factura(factura_id):
    """
    Permite modificar el detalle del pedido y los datos de una factura ya ingresada.
    """
    distribuidor_id = request.form.get("distribuidor_id")
    numero_factura = request.form.get("numero_factura", "").strip()
    fecha = request.form.get("fecha", "").strip()
    tipo_frecuencia = request.form.get("tipo_frecuencia", "").strip()
    detalle_pedido = request.form.get("detalle_pedido", "").strip()
    monto = request.form.get("monto", "0").strip()
    medio_pago = request.form.get("medio_pago", "").strip()

    if not (distribuidor_id and numero_factura and fecha and tipo_frecuencia and detalle_pedido and monto and medio_pago):
        flash("Todos los campos de la factura y el detalle del pedido son obligatorios.", "danger")
        return redirect(url_for("index"))

    try:
        monto_entero = int(float(monto))
    except ValueError:
        flash("El monto a cancelar debe ser un valor numérico válido.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("""
        UPDATE facturas
        SET distribuidor_id = ?, numero_factura = ?, fecha = ?, tipo_frecuencia = ?, detalle_pedido = ?, monto = ?, medio_pago = ?
        WHERE id = ?
    """, (int(distribuidor_id), numero_factura, fecha, tipo_frecuencia, detalle_pedido, monto_entero, medio_pago, factura_id))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    mes_factura = fecha[:7]
    flash(f"Factura N° {numero_factura} actualizada correctamente.", "success")
    return redirect(url_for("index", mes=mes_factura))


@app.route("/factura/eliminar/<int:factura_id>", methods=["POST"])
def eliminar_factura(factura_id):
    """
    Permite eliminar una factura en caso de error de digitación.
    """
    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("DELETE FROM facturas WHERE id = ?", (factura_id,))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    flash("Factura eliminada correctamente.", "warning")
    return redirect(url_for("index"))


@app.route("/distribuidor/editar/<int:distribuidor_id>", methods=["POST"])
def editar_distribuidor(distribuidor_id):
    """
    Permite modificar los datos de un proveedor/distribuidor ya registrado.
    """
    nombre = request.form.get("nombre", "").strip()
    rut_empresa = request.form.get("rut_empresa", "").strip()
    telefono = request.form.get("telefono", "").strip()
    rubro_insumo = request.form.get("rubro_insumo", "").strip()

    if not nombre or not rubro_insumo:
        flash("El nombre del proveedor y su rubro de insumos son obligatorios.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("""
        UPDATE distribuidores
        SET nombre = ?, rut_empresa = ?, telefono = ?, rubro_insumo = ?
        WHERE id = ?
    """, (nombre, rut_empresa, telefono, rubro_insumo, distribuidor_id))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    flash(f"Proveedor '{nombre}' modificado correctamente.", "success")
    return redirect(url_for("index"))


@app.route("/distribuidor/eliminar/<int:distribuidor_id>", methods=["POST"])
def eliminar_distribuidor(distribuidor_id):
    """
    Permite eliminar un distribuidor y sus facturas asociadas.
    """
    conn = get_db_connection()
    restaurar_desde_formulario_si_necesario(conn)
    conn.execute("DELETE FROM facturas WHERE distribuidor_id = ?", (distribuidor_id,))
    conn.execute("DELETE FROM distribuidores WHERE id = ?", (distribuidor_id,))
    actualizar_version_datos(conn)
    conn.commit()
    guardar_respaldo_nube(conn)
    conn.close()

    flash("Distribuidor eliminado del registro.", "warning")
    return redirect(url_for("index"))


# Filtro personalizado para formatear pesos chilenos / moneda de forma legible (ej: $245.000)
@app.template_filter("moneda")
def formato_moneda(valor):
    try:
        return "${:,.0f}".format(int(valor)).replace(",", ".")
    except (ValueError, TypeError):
        return "$0"


# Inicializamos la base de datos automáticamente al arrancar la aplicación
# (Esto es fundamental cuando se despliega en servidores en la nube con Gunicorn como Render)
init_db()


if __name__ == "__main__":
    app.run(debug=True, port=5000)

