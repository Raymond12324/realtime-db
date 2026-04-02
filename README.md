# Sistema de Base de Datos en Tiempo Real con Interfaz Web

## Documento de Entrega Académica

**Asignatura:** Programación en Tiempo Real  
**Universidad:** UNIBE  
**Tecnologías:** Python · Flask · SQLite · HTML/CSS/JS · threading

---

## 1. Descripción del Sistema

Este sistema es un **inventario en tiempo real** donde múltiples procesos (hilos/threads) pueden registrar ventas de forma simultánea mientras la base de datos mantiene la **consistencia** de los datos. El dashboard web muestra productos, stock actualizado, y un log de eventos en tiempo real.

El problema central que resuelve: **¿Cómo garantizar que los datos sean correctos cuando múltiples usuarios acceden y modifican la base de datos al mismo tiempo?**

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────┐
│                    NAVEGADOR WEB                     │
│  ┌─────────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Dashboard   │ │ Formulario│ │  Panel Eventos   │  │
│  │  (tabla,     │ │ (agregar  │ │  (log en tiempo  │  │
│  │   stats)     │ │  producto)│ │   real)          │  │
│  └──────┬───────┘ └────┬─────┘ └────────┬─────────┘  │
│         │    fetch() cada 3s    │        │            │
└─────────┼───────────────────────┼────────┼────────────┘
          │         HTTP/JSON     │        │
          ▼                       ▼        ▼
┌─────────────────────────────────────────────────────┐
│                  FLASK (app.py)                       │
│                                                       │
│  /api/productos  /api/venta  /api/simular            │
│  /api/eventos    /api/stats  /api/reset              │
│                                                       │
│  ┌─────────────────────────────────────────┐         │
│  │     SIMULACIÓN DE CONCURRENCIA          │         │
│  │                                         │         │
│  │  Thread-1 ──┐                           │         │
│  │  Thread-2 ──┤                           │         │
│  │  Thread-3 ──┼──→ procesar_venta()       │         │
│  │  ...        │    (protegida con Lock)   │         │
│  │  Thread-N ──┘                           │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              database.py + SQLite                     │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │productos │  │ ventas   │  │ eventos  │           │
│  │----------│  │----------│  │----------│           │
│  │id        │  │id        │  │id        │           │
│  │nombre    │  │producto_id│ │descripcion│           │
│  │stock     │  │cantidad  │  │timestamp │           │
│  │precio    │  │fecha     │  │          │           │
│  └──────────┘  └──────────┘  └──────────┘           │
│                                                       │
│  🔒 threading.Lock → Sección crítica protegida       │
│  📝 PRAGMA WAL → Better concurrency en SQLite        │
│  🔄 Transacciones → Atomicidad (commit/rollback)     │
└─────────────────────────────────────────────────────┘
```

---

## 3. Estructura del Proyecto

```
realtime-db/
├── app.py              ← Servidor Flask + rutas API + simulación
├── database.py         ← Módulo de BD + Lock + transacciones
├── templates/
│   └── index.html      ← Dashboard HTML
└── static/
    ├── style.css       ← Estilos del dashboard
    └── script.js       ← Lógica frontend (fetch, polling)
```

---

## 4. Instrucciones de Ejecución

### Requisitos previos
- Python 3.8 o superior instalado
- pip (gestor de paquetes de Python)

### Pasos

```bash
# 1. Abrir terminal en la carpeta del proyecto
cd realtime-db

# 2. Instalar Flask (única dependencia)
pip install flask

# 3. Ejecutar el servidor
python app.py
```

El servidor arranca en: **http://127.0.0.1:5000**

Abrir esa URL en el navegador. La base de datos se crea automáticamente con 6 productos de ejemplo.

---

## 5. Ejemplo de Uso

1. **Al abrir:** Se muestra el dashboard con 6 productos, estadísticas y log de eventos.
2. **Agregar producto:** Llenar el formulario lateral y presionar "Agregar Producto".
3. **Venta individual:** Presionar "Vender 1" en cualquier producto de la tabla.
4. **Simulación de concurrencia:**
   - Configurar: 8 hilos, 2 unidades por venta
   - Presionar "Simular Ventas Concurrentes"
   - Observar: los resultados muestran cuántas ventas fueron exitosas y cuántas rechazadas por stock insuficiente
   - El log de eventos muestra cada operación con su hilo identificado
5. **Reiniciar:** El botón "Reiniciar DB" restaura todo al estado inicial.

---

## 6. Explicación Académica: Conceptos Demostrados

### 6.1 Programación en Tiempo Real (Simulación)

El sistema simula un entorno en tiempo real de dos formas:
- **Backend:** Múltiples hilos ejecutan ventas al mismo tiempo, como si fueran usuarios simultáneos.
- **Frontend:** Un polling cada 3 segundos actualiza automáticamente la interfaz sin recargar la página.

Aunque no es "tiempo real duro" (hard real-time), demuestra el patrón de sistemas reactivos que responden a eventos conforme ocurren.

### 6.2 Manejo de Eventos

Cada acción del sistema genera un **evento** que se almacena en la tabla `eventos`:
- Producto agregado → evento registrado
- Venta exitosa → evento con detalles del hilo, stock anterior y nuevo
- Venta rechazada → evento de error con razón
- Simulación iniciada/completada → eventos informativos

El frontend consulta estos eventos periódicamente y los muestra en un log visual.

### 6.3 Concurrencia

La concurrencia se implementa con `threading.Thread`:

```python
# Se crean N hilos, cada uno ejecuta worker_venta()
hilos = []
for i in range(num_hilos):
    t = threading.Thread(target=worker_venta, args=(f"T-{i+1}",))
    hilos.append(t)

# Se lanzan todos (ejecución concurrente)
for t in hilos:
    t.start()

# Se espera a que todos terminen
for t in hilos:
    t.join()
```

Cada hilo simula un "usuario" que intenta comprar un producto al mismo tiempo que otros hilos.

### 6.4 Sincronización (Lock)

Sin sincronización, ocurre una **condición de carrera**:

```
Hilo A lee stock = 5
Hilo B lee stock = 5      ← Lee ANTES de que A actualice
Hilo A actualiza stock = 3 (vendió 2)
Hilo B actualiza stock = 3 (vendió 2) ← ¡Debería ser 1!
```

Con `threading.Lock`:

```python
db_lock = threading.Lock()

def procesar_venta(producto_id, cantidad, thread_id):
    with db_lock:  # Solo un hilo entra aquí a la vez
        # Leer stock
        # Verificar disponibilidad
        # Actualizar stock
        # Registrar venta
        # Commit
```

El `with db_lock` garantiza **exclusión mutua**: solo un hilo puede ejecutar la sección crítica. Los demás esperan su turno.

### 6.5 Transacciones en Base de Datos

SQLite maneja transacciones con COMMIT y ROLLBACK:

- **COMMIT:** Si toda la operación (verificar stock + actualizar + registrar venta) es exitosa, se confirman todos los cambios juntos.
- **ROLLBACK:** Si ocurre cualquier error, se deshacen todos los cambios, dejando la BD en estado consistente.

Además, se usa `PRAGMA journal_mode=WAL` (Write-Ahead Logging) para mejorar la concurrencia de lectura/escritura en SQLite.

### 6.6 Consistencia de Datos

La consistencia se garantiza por tres mecanismos trabajando juntos:

1. **Lock:** Evita que dos hilos lean/modifiquen el stock al mismo tiempo.
2. **Verificación de stock:** Se verifica `stock >= cantidad` DENTRO del Lock, antes de vender.
3. **Transacciones:** Si algo falla a mitad del proceso, el ROLLBACK deshace todo.

Resultado: **el stock nunca puede ser negativo**, sin importar cuántos hilos intenten comprar simultáneamente.

---

## 7. Guion para Exposición (5-7 minutos)

### Slide 1 — Problema (30 seg)
> "Imaginen un sistema de inventario donde 10 personas intentan comprar el último producto al mismo tiempo. Sin control, el sistema podría vender más unidades de las que hay, dejando un stock negativo. Este es el problema de la **condición de carrera** en programación concurrente."

### Slide 2 — Solución (30 seg)
> "Desarrollamos un sistema de inventario web que usa **threading** para simular múltiples usuarios comprando simultáneamente, y **threading.Lock** para garantizar que los datos sean siempre correctos."

### Slide 3 — Demostración en vivo (2 min)
> *Abrir el navegador en localhost:5000*
> "Aquí vemos el dashboard con 6 productos. Voy a simular 10 hilos comprando al mismo tiempo..."
> *Presionar Simular con 10 hilos, 5 unidades*
> "Observen: algunas ventas se completaron y otras fueron rechazadas por stock insuficiente. El stock nunca quedó negativo."

### Slide 4 — Dónde está la concurrencia (1 min)
> "La concurrencia está en `app.py`, endpoint `/api/simular`. Se crean N objetos `threading.Thread`, cada uno apuntando a una función que intenta hacer una venta. Se lanzan todos con `.start()` y se espera con `.join()`. Esto simula N usuarios accediendo a la base de datos al mismo tiempo."

### Slide 5 — Dónde está la sincronización (1 min)
> "La sincronización está en `database.py`, función `procesar_venta()`. Usamos `threading.Lock` con la sentencia `with db_lock:`. Esto crea una **sección crítica**: solo un hilo puede leer el stock, verificarlo, actualizarlo y registrar la venta. Los demás hilos esperan en cola."

### Slide 6 — Cómo se garantiza la consistencia (1 min)
> "Tres mecanismos:
> 1. El **Lock** evita acceso simultáneo al stock.
> 2. La **verificación** `if stock < cantidad` dentro del Lock previene stock negativo.
> 3. Las **transacciones** de SQLite (commit/rollback) aseguran que si algo falla, no queden datos a medias."

### Slide 7 — Lo que aprendí (30 seg)
> "Con este proyecto comprendí que la concurrencia sin control causa errores silenciosos que son difíciles de depurar. El uso de Locks y transacciones es fundamental en cualquier sistema donde múltiples procesos acceden a datos compartidos: desde un inventario hasta un sistema bancario."

---

## 8. Tecnologías Utilizadas

| Tecnología | Uso |
|---|---|
| Python 3 | Lenguaje principal del backend |
| Flask | Servidor web y API REST |
| SQLite | Base de datos (archivo local) |
| threading | Creación de hilos concurrentes |
| threading.Lock | Sincronización / exclusión mutua |
| HTML5 | Estructura del dashboard |
| CSS3 | Estilos visuales modernos |
| JavaScript | Lógica frontend, fetch API, polling |

---

*Sistema desarrollado como proyecto académico para demostrar conceptos de programación en tiempo real, concurrencia y sincronización de bases de datos.*
