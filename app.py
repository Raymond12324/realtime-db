"""
app.py - Servidor Flask del Sistema de Base de Datos en Tiempo Real
====================================================================
Este archivo implementa:
  - Servidor web con Flask
  - API REST para productos, ventas y eventos
  - Simulación de concurrencia con threading
  - Endpoint para lanzar ventas concurrentes simultáneas
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
import random
from database import (
    init_db,
    obtener_productos,
    agregar_producto,
    procesar_venta,
    obtener_eventos,
    obtener_estadisticas,
    registrar_evento,
    resetear_db,
)

app = Flask(__name__)


# ============================================================
# RUTA PRINCIPAL - Sirve el dashboard
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# API: Obtener productos
# ============================================================
@app.route("/api/productos", methods=["GET"])
def api_productos():
    productos = obtener_productos()
    return jsonify(productos)


# ============================================================
# API: Agregar producto
# ============================================================
@app.route("/api/productos", methods=["POST"])
def api_agregar_producto():
    data = request.get_json()
    nombre = data.get("nombre", "").strip()
    stock = data.get("stock", 0)
    precio = data.get("precio", 0.0)

    if not nombre:
        return jsonify({"success": False, "message": "El nombre es requerido"}), 400
    if stock < 0 or precio < 0:
        return jsonify({"success": False, "message": "Stock y precio deben ser >= 0"}), 400

    resultado = agregar_producto(nombre, int(stock), float(precio))
    return jsonify(resultado)


# ============================================================
# API: Procesar una venta individual
# ============================================================
@app.route("/api/venta", methods=["POST"])
def api_venta():
    data = request.get_json()
    producto_id = data.get("producto_id")
    cantidad = data.get("cantidad", 1)

    if not producto_id or cantidad < 1:
        return jsonify({"success": False, "message": "Datos inválidos"}), 400

    resultado = procesar_venta(int(producto_id), int(cantidad), "web")
    return jsonify(resultado)


# ============================================================
# API: Simular ventas concurrentes (FUNCIÓN CLAVE)
# ============================================================
@app.route("/api/simular", methods=["POST"])
def api_simular():
    """
    ================================================================
    SIMULACIÓN DE CONCURRENCIA
    ================================================================
    Este endpoint demuestra el concepto central del proyecto:
    - Crea N hilos (threads) que ejecutan ventas SIMULTÁNEAMENTE
    - Cada hilo intenta comprar un producto aleatorio
    - El threading.Lock en database.py garantiza consistencia
    - Se recopilan todos los resultados al finalizar

    Flujo:
    1. Se reciben parámetros (num_hilos, cantidad por venta)
    2. Se crean N threads apuntando a worker_venta()
    3. Se lanzan TODOS a la vez (.start())
    4. Se espera a que TODOS terminen (.join())
    5. Se devuelven los resultados consolidados
    ================================================================
    """
    data = request.get_json()
    num_hilos = min(data.get("num_hilos", 5), 20)  # Máximo 20 hilos
    cantidad = data.get("cantidad", 1)

    productos = obtener_productos()
    if not productos:
        return jsonify({"success": False, "message": "No hay productos"})

    resultados = []
    resultados_lock = threading.Lock()  # Lock para la lista de resultados

    registrar_evento(
        f"🚀 SIMULACIÓN INICIADA: {num_hilos} hilos, {cantidad} unidad(es) cada uno"
    )

    def worker_venta(thread_id):
        """
        Función que ejecuta cada hilo.
        Selecciona un producto aleatorio e intenta comprarlo.
        """
        # Pequeño delay aleatorio para simular usuarios reales
        time.sleep(random.uniform(0.01, 0.1))

        # Elegir producto aleatorio
        producto = random.choice(productos)
        resultado = procesar_venta(producto["id"], cantidad, thread_id)

        # Guardar resultado de forma segura (con su propio Lock)
        with resultados_lock:
            resultados.append(
                {
                    "thread_id": thread_id,
                    "producto": producto["nombre"],
                    "resultado": resultado,
                }
            )

    # ----------------------------------------------------------
    # CREAR Y LANZAR HILOS
    # ----------------------------------------------------------
    hilos = []
    for i in range(num_hilos):
        t = threading.Thread(
            target=worker_venta,
            args=(f"T-{i+1:02d}",),
            name=f"VentaThread-{i+1}",
        )
        hilos.append(t)

    # Iniciar todos los hilos (ejecución concurrente)
    for t in hilos:
        t.start()

    # Esperar a que todos terminen (sincronización)
    for t in hilos:
        t.join()

    # Contar resultados
    exitosas = sum(1 for r in resultados if r["resultado"]["success"])
    fallidas = len(resultados) - exitosas

    registrar_evento(
        f"✅ SIMULACIÓN COMPLETADA: {exitosas} exitosas, {fallidas} rechazadas"
    )

    return jsonify(
        {
            "success": True,
            "total_hilos": num_hilos,
            "exitosas": exitosas,
            "fallidas": fallidas,
            "resultados": resultados,
        }
    )


# ============================================================
# API: Obtener eventos recientes
# ============================================================
@app.route("/api/eventos", methods=["GET"])
def api_eventos():
    eventos = obtener_eventos()
    return jsonify(eventos)


# ============================================================
# API: Obtener estadísticas
# ============================================================
@app.route("/api/stats", methods=["GET"])
def api_stats():
    stats = obtener_estadisticas()
    return jsonify(stats)


# ============================================================
# API: Resetear base de datos
# ============================================================
@app.route("/api/reset", methods=["POST"])
def api_reset():
    resetear_db()
    return jsonify({"success": True, "message": "Base de datos reiniciada"})


# ============================================================
# INICIAR SERVIDOR
# ============================================================
if __name__ == "__main__":
    # Inicializar la base de datos al arrancar
    init_db()
    print("=" * 60)
    print("  Sistema de Base de Datos en Tiempo Real")
    print("  Servidor iniciado en: http://127.0.0.1:5000")
    print("=" * 60)

    # debug=False es importante para que threading funcione correctamente
    # threaded=True permite manejar múltiples requests HTTP simultáneos
    app.run(debug=False, threaded=True, port=5000)
