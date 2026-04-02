"""
database.py - Módulo de Base de Datos en Tiempo Real
=====================================================
Este módulo maneja toda la interacción con SQLite.
Implementa:
  - Creación de tablas (productos, ventas, eventos)
  - Operaciones CRUD con transacciones
  - threading.Lock para sincronización
  - Protección contra condiciones de carrera
"""

import sqlite3
import threading
from datetime import datetime

# ============================================================
# LOCK GLOBAL - Sincronización entre hilos
# ============================================================
# Este Lock garantiza que solo UN hilo a la vez pueda
# modificar el stock o registrar una venta.
# Sin esto, dos hilos podrían leer el mismo stock
# y ambos vender, causando inconsistencia (stock negativo).
db_lock = threading.Lock()

DATABASE = "inventario.db"


def get_connection():
    """
    Crea una conexión a SQLite.
    Cada hilo necesita su propia conexión porque SQLite
    no permite compartir conexiones entre hilos.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging: mejor concurrencia
    conn.execute("PRAGMA busy_timeout=5000")  # Esperar hasta 5s si la DB está bloqueada
    return conn


def init_db():
    """
    Inicializa la base de datos creando las 3 tablas requeridas
    e insertando datos de ejemplo si está vacía.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------------------------------------
    # TABLA 1: productos
    # Almacena el inventario con stock y precio
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            stock INTEGER NOT NULL DEFAULT 0,
            precio REAL NOT NULL DEFAULT 0.0
        )
    """)

    # ----------------------------------------------------------
    # TABLA 2: ventas
    # Registra cada venta con referencia al producto
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    """)

    # ----------------------------------------------------------
    # TABLA 3: eventos
    # Log de eventos del sistema en tiempo real
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()

    # Insertar datos de ejemplo si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] == 0:
        productos_iniciales = [
            ("Laptop HP Pavilion", 25, 45999.99),
            ("Monitor Samsung 27\"", 40, 18500.00),
            ("Teclado Mecánico RGB", 60, 3200.00),
            ("Mouse Inalámbrico", 80, 1500.00),
            ("Auriculares Bluetooth", 50, 2800.00),
            ("Webcam HD 1080p", 35, 4200.00),
        ]
        cursor.executemany(
            "INSERT INTO productos (nombre, stock, precio) VALUES (?, ?, ?)",
            productos_iniciales,
        )
        conn.commit()

        # Registrar evento inicial
        registrar_evento_interno(
            cursor, "Sistema inicializado con 6 productos de ejemplo"
        )
        conn.commit()

    conn.close()


def registrar_evento_interno(cursor, descripcion):
    """Registra un evento usando un cursor existente (dentro de una transacción)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    cursor.execute(
        "INSERT INTO eventos (descripcion, timestamp) VALUES (?, ?)",
        (descripcion, timestamp),
    )


def registrar_evento(descripcion):
    """Registra un evento en su propia transacción."""
    conn = get_connection()
    cursor = conn.cursor()
    registrar_evento_interno(cursor, descripcion)
    conn.commit()
    conn.close()


def obtener_productos():
    """Retorna la lista completa de productos."""
    conn = get_connection()
    productos = conn.execute(
        "SELECT id, nombre, stock, precio FROM productos ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(p) for p in productos]


def agregar_producto(nombre, stock, precio):
    """
    Agrega un nuevo producto al inventario.
    Usa Lock para evitar duplicados por concurrencia.
    """
    with db_lock:  # <-- SINCRONIZACIÓN
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO productos (nombre, stock, precio) VALUES (?, ?, ?)",
                (nombre, stock, precio),
            )
            conn.commit()
            registrar_evento(f"Producto agregado: {nombre} (stock: {stock})")
            return {"success": True, "message": f"Producto '{nombre}' agregado"}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"El producto '{nombre}' ya existe"}
        finally:
            conn.close()


def procesar_venta(producto_id, cantidad, thread_id="main"):
    """
    ================================================================
    FUNCIÓN CRÍTICA - Procesa una venta con sincronización
    ================================================================
    Esta función demuestra:
    1. threading.Lock → Solo un hilo entra a la vez
    2. Transacciones → BEGIN/COMMIT garantizan atomicidad
    3. Verificación de stock → Previene stock negativo
    4. Registro de evento → Trazabilidad en tiempo real

    Sin el Lock, dos hilos podrían:
      - Hilo A lee stock = 5
      - Hilo B lee stock = 5
      - Hilo A vende 3, stock = 2
      - Hilo B vende 3, stock = 2  ← ¡ERROR! Debería ser -1
    Con el Lock:
      - Hilo A adquiere lock, lee stock=5, vende 3, stock=2, libera lock
      - Hilo B adquiere lock, lee stock=2, vende 3 → rechazado (2 < 3)
    ================================================================
    """
    with db_lock:  # <-- SECCIÓN CRÍTICA: solo un hilo a la vez
        conn = get_connection()
        try:
            # PASO 1: Leer stock actual (dentro del lock)
            producto = conn.execute(
                "SELECT id, nombre, stock FROM productos WHERE id = ?",
                (producto_id,),
            ).fetchone()

            if not producto:
                return {
                    "success": False,
                    "message": f"[Hilo {thread_id}] Producto no encontrado",
                }

            nombre = producto["nombre"]
            stock_actual = producto["stock"]

            # PASO 2: Verificar disponibilidad (NO permitir stock negativo)
            if stock_actual < cantidad:
                msg = (
                    f"[Hilo {thread_id}] Stock insuficiente para '{nombre}': "
                    f"disponible={stock_actual}, solicitado={cantidad}"
                )
                registrar_evento_interno(conn.cursor(), f"⚠ RECHAZADO: {msg}")
                conn.commit()
                return {"success": False, "message": msg}

            # PASO 3: Actualizar stock (TRANSACCIÓN)
            nuevo_stock = stock_actual - cantidad
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE productos SET stock = ? WHERE id = ?",
                (nuevo_stock, producto_id),
            )

            # PASO 4: Registrar la venta
            cursor.execute(
                "INSERT INTO ventas (producto_id, cantidad, fecha) VALUES (?, ?, ?)",
                (producto_id, cantidad, fecha),
            )

            # PASO 5: Registrar evento
            registrar_evento_interno(
                cursor,
                f"✓ VENTA [Hilo {thread_id}]: {cantidad}x '{nombre}' → "
                f"stock: {stock_actual} → {nuevo_stock}",
            )

            # PASO 6: Confirmar transacción (COMMIT)
            conn.commit()

            return {
                "success": True,
                "message": (
                    f"[Hilo {thread_id}] Venta exitosa: {cantidad}x '{nombre}' "
                    f"(stock: {stock_actual} → {nuevo_stock})"
                ),
            }

        except Exception as e:
            conn.rollback()  # ROLLBACK si algo falla
            return {"success": False, "message": f"[Hilo {thread_id}] Error: {str(e)}"}
        finally:
            conn.close()


def obtener_eventos(limite=50):
    """Retorna los eventos más recientes."""
    conn = get_connection()
    eventos = conn.execute(
        "SELECT id, descripcion, timestamp FROM eventos ORDER BY id DESC LIMIT ?",
        (limite,),
    ).fetchall()
    conn.close()
    return [dict(e) for e in eventos]


def obtener_estadisticas():
    """Retorna estadísticas generales del sistema."""
    conn = get_connection()
    stats = {}
    stats["total_productos"] = conn.execute(
        "SELECT COUNT(*) FROM productos"
    ).fetchone()[0]
    stats["total_ventas"] = conn.execute(
        "SELECT COUNT(*) FROM ventas"
    ).fetchone()[0]
    stats["stock_total"] = (
        conn.execute("SELECT COALESCE(SUM(stock), 0) FROM productos").fetchone()[0]
    )
    stats["valor_inventario"] = (
        conn.execute(
            "SELECT COALESCE(SUM(stock * precio), 0) FROM productos"
        ).fetchone()[0]
    )
    conn.close()
    return stats


def resetear_db():
    """Elimina todos los datos y reinicializa la base de datos."""
    conn = get_connection()
    conn.execute("DELETE FROM eventos")
    conn.execute("DELETE FROM ventas")
    conn.execute("DELETE FROM productos")
    conn.commit()
    conn.close()
    init_db()
