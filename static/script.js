/**
 * script.js - Lógica del Frontend
 * ==================================
 * Maneja:
 *  - Polling automático para actualizar datos
 *  - Envío de formularios via fetch (AJAX)
 *  - Simulación de ventas concurrentes
 *  - Notificaciones toast
 *  - Actualización del DOM en tiempo real
 */

// ============================================================
// ESTADO GLOBAL
// ============================================================
let pollingInterval = null;
let isSimulating = false;

// ============================================================
// INICIALIZACIÓN
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  cargarDatos();
  iniciarPolling();
});

/**
 * Inicia el polling automático cada 3 segundos.
 * Esto simula "tiempo real" sin necesidad de WebSockets.
 */
function iniciarPolling() {
  pollingInterval = setInterval(() => {
    if (!isSimulating) {
      cargarDatos();
    }
  }, 3000);
}

/**
 * Carga todos los datos: estadísticas, productos y eventos.
 */
async function cargarDatos() {
  try {
    const [statsRes, prodRes, eventRes] = await Promise.all([
      fetch("/api/stats"),
      fetch("/api/productos"),
      fetch("/api/eventos"),
    ]);

    const stats = await statsRes.json();
    const productos = await prodRes.json();
    const eventos = await eventRes.json();

    renderizarStats(stats);
    renderizarProductos(productos);
    renderizarEventos(eventos);
  } catch (err) {
    console.error("Error cargando datos:", err);
  }
}

// ============================================================
// RENDERIZADO DE ESTADÍSTICAS
// ============================================================
function renderizarStats(stats) {
  document.getElementById("stat-productos").textContent = stats.total_productos;
  document.getElementById("stat-ventas").textContent = stats.total_ventas;
  document.getElementById("stat-stock").textContent = stats.stock_total.toLocaleString();
  document.getElementById("stat-valor").textContent =
    "$" + Number(stats.valor_inventario).toLocaleString("es-DO", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
}

// ============================================================
// RENDERIZADO DE TABLA DE PRODUCTOS
// ============================================================
function renderizarProductos(productos) {
  const tbody = document.getElementById("productos-body");

  if (productos.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="empty-state">No hay productos registrados</td>
      </tr>`;
    return;
  }

  tbody.innerHTML = productos
    .map((p) => {
      // Determinar clase del badge según nivel de stock
      let badgeClass = "stock-ok";
      if (p.stock === 0) badgeClass = "stock-out";
      else if (p.stock <= 10) badgeClass = "stock-low";

      return `
        <tr>
          <td style="color: var(--text-muted); font-family: var(--font-mono); font-size: 12px;">#${p.id}</td>
          <td class="product-name">${escapeHtml(p.nombre)}</td>
          <td><span class="stock-badge ${badgeClass}">${p.stock}</span></td>
          <td class="price">$${Number(p.precio).toLocaleString("es-DO", { minimumFractionDigits: 2 })}</td>
          <td>
            <button class="btn btn-sm btn-ghost" onclick="ventaRapida(${p.id}, '${escapeHtml(p.nombre)}')"
              ${p.stock === 0 ? "disabled" : ""}>
              Vender 1
            </button>
          </td>
        </tr>`;
    })
    .join("");
}

// ============================================================
// RENDERIZADO DE EVENTOS
// ============================================================
function renderizarEventos(eventos) {
  const container = document.getElementById("eventos-list");

  if (eventos.length === 0) {
    container.innerHTML = `<div class="empty-state">No hay eventos registrados</div>`;
    return;
  }

  container.innerHTML = eventos
    .map((e) => {
      // Clasificar tipo de evento para color
      let descClass = "";
      if (e.descripcion.includes("✓") || e.descripcion.includes("✅"))
        descClass = "success";
      else if (e.descripcion.includes("⚠") || e.descripcion.includes("RECHAZADO"))
        descClass = "error";
      else if (e.descripcion.includes("🚀") || e.descripcion.includes("Sistema"))
        descClass = "info";

      return `
        <div class="event-item">
          <div class="event-time">${e.timestamp}</div>
          <div class="event-desc ${descClass}">${escapeHtml(e.descripcion)}</div>
        </div>`;
    })
    .join("");
}

// ============================================================
// AGREGAR PRODUCTO
// ============================================================
async function agregarProducto(event) {
  event.preventDefault();

  const nombre = document.getElementById("prod-nombre").value.trim();
  const stock = parseInt(document.getElementById("prod-stock").value);
  const precio = parseFloat(document.getElementById("prod-precio").value);

  if (!nombre || isNaN(stock) || isNaN(precio)) {
    mostrarToast("Complete todos los campos correctamente", "error");
    return;
  }

  try {
    const res = await fetch("/api/productos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, stock, precio }),
    });

    const data = await res.json();

    if (data.success) {
      mostrarToast(data.message, "success");
      document.getElementById("form-producto").reset();
      cargarDatos();
    } else {
      mostrarToast(data.message, "error");
    }
  } catch (err) {
    mostrarToast("Error de conexión", "error");
  }
}

// ============================================================
// VENTA RÁPIDA (1 unidad)
// ============================================================
async function ventaRapida(productoId, nombre) {
  try {
    const res = await fetch("/api/venta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ producto_id: productoId, cantidad: 1 }),
    });

    const data = await res.json();
    mostrarToast(data.message, data.success ? "success" : "error");
    cargarDatos();
  } catch (err) {
    mostrarToast("Error de conexión", "error");
  }
}

// ============================================================
// SIMULACIÓN DE VENTAS CONCURRENTES
// ============================================================
async function simularVentas() {
  if (isSimulating) return;

  const numHilos = parseInt(document.getElementById("sim-hilos").value) || 5;
  const cantidad = parseInt(document.getElementById("sim-cantidad").value) || 1;

  const btn = document.getElementById("btn-simular");
  const resultsDiv = document.getElementById("sim-results");

  // Estado de carga
  isSimulating = true;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Simulando ${numHilos} hilos...`;
  resultsDiv.innerHTML = "";

  try {
    const res = await fetch("/api/simular", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ num_hilos: numHilos, cantidad }),
    });

    const data = await res.json();

    // Mostrar resultados
    if (data.success) {
      let html = `
        <div class="sim-results-header">
          <span class="sim-badge ok">✓ ${data.exitosas} exitosas</span>
          <span class="sim-badge fail">✕ ${data.fallidas} rechazadas</span>
        </div>
        <div style="max-height: 200px; overflow-y: auto;">`;

      data.resultados.forEach((r) => {
        const cls = r.resultado.success ? "ok" : "fail";
        const icon = r.resultado.success ? "✓" : "✕";
        html += `<div class="sim-result-item ${cls}">${icon} ${r.resultado.message}</div>`;
      });

      html += "</div>";
      resultsDiv.innerHTML = html;

      mostrarToast(
        `Simulación completada: ${data.exitosas}/${data.total_hilos} exitosas`,
        data.exitosas > 0 ? "success" : "error"
      );
    }

    // Actualizar datos
    cargarDatos();
  } catch (err) {
    mostrarToast("Error en la simulación", "error");
  } finally {
    isSimulating = false;
    btn.disabled = false;
    btn.innerHTML = "▶ Simular Ventas Concurrentes";
  }
}

// ============================================================
// RESETEAR BASE DE DATOS
// ============================================================
async function resetearDB() {
  if (!confirm("¿Está seguro de reiniciar toda la base de datos?")) return;

  try {
    const res = await fetch("/api/reset", { method: "POST" });
    const data = await res.json();
    mostrarToast(data.message, "success");
    document.getElementById("sim-results").innerHTML = "";
    cargarDatos();
  } catch (err) {
    mostrarToast("Error al reiniciar", "error");
  }
}

// ============================================================
// SISTEMA DE NOTIFICACIONES (TOAST)
// ============================================================
function mostrarToast(mensaje, tipo = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  toast.textContent = mensaje;
  container.appendChild(toast);

  // Remover después de 3 segundos
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// ============================================================
// UTILIDADES
// ============================================================
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
