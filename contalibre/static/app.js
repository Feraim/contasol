/* ContaLibre — interfaz estilo aplicación de escritorio con cinta de opciones.
   Sin dependencias; habla con la API REST en /api/v1. */
"use strict";

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

let empresaActual = null; // id de la empresa activa
let miPerfil = null; // { id, email, nombre, empresas: [{id, nombre, rol}] }

async function api(path, opts = {}) {
  const cabeceras = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (empresaActual != null) cabeceras["X-Empresa-Id"] = String(empresaActual);
  const res = await fetch("/api/v1" + path, {
    credentials: "same-origin",
    ...opts,
    headers: cabeceras,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : res.statusText);
  }
  return data;
}

const eur = (n) => (n ?? 0).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
const fecha_es = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
const hoy = () => new Date().toISOString().slice(0, 10);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let toastTimer;
function toast(msg, error = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = error ? "error" : "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("oculto"), error ? 6000 : 3000);
}
const fallo = (e) => toast(e.message || String(e), true);

function abrirModal(titulo, html) {
  $("#modal-titulo-texto").textContent = titulo;
  $("#modal-contenido").innerHTML = html;
  $("#modal").classList.remove("oculto");
}
const cerrarModal = () => $("#modal").classList.add("oculto");
$("#modal-cerrar").onclick = cerrarModal;
$("#modal").onclick = (e) => { if (e.target.id === "modal") cerrarModal(); };

/* ---------- estado global ---------- */

let ejercicio = new Date().getFullYear();
let cuentas = new Map(); // codigo → nombre
let vistaActual = "inicio";
const desdeEj = () => `${ejercicio}-01-01`;
const hastaEj = () => `${ejercicio}-12-31`;

async function recargarCuentas() {
  const lista = await api("/cuentas");
  cuentas = new Map(lista.map((c) => [c.codigo, c.nombre]));
  $("#dl-cuentas").innerHTML = lista
    .map((c) => `<option value="${esc(c.codigo)}">${esc(c.nombre)}</option>`)
    .join("");
}

/* ---------- cinta de opciones ---------- */

const RIBBON = [
  {
    id: "inicio", label: "Inicio",
    grupos: [
      { etiqueta: "Vista general", botones: [["📊", "Resumen", "inicio"]] },
      { etiqueta: "Diario", botones: [["📝", "Introducir asientos", "nuevoAsiento"], ["📖", "Consulta de diario", "diario"]] },
      { etiqueta: "Facturación", botones: [["🧾", "Facturas emitidas", "emitidas"], ["📄", "Facturas recibidas", "recibidas"]] },
    ],
  },
  {
    id: "asistente", label: "Asistente IA",
    grupos: [
      { etiqueta: "Preguntas", botones: [["🤖", "Preguntar a la IA", "asistente"]] },
    ],
  },
  {
    id: "diario", label: "Diario",
    grupos: [
      { etiqueta: "Asientos", botones: [["📝", "Introducir asientos", "nuevoAsiento"], ["📖", "Consulta de diario", "diario"]] },
      { etiqueta: "Consultas", botones: [["📚", "Extracto de mayor", "mayor"], ["⚖️", "Sumas y saldos", "sumas"]] },
      { etiqueta: "Ficheros", botones: [["🗂️", "P.G.C.", "pgc"], ["👥", "Clientes / Proveedores", "terceros"]] },
    ],
  },
  {
    id: "facturacion", label: "Facturación",
    grupos: [
      { etiqueta: "IVA repercutido", botones: [["🧾", "Facturas emitidas", "emitidas"]] },
      { etiqueta: "IVA soportado", botones: [["📄", "Facturas recibidas", "recibidas"]] },
      { etiqueta: "Impuestos", botones: [["🏛️", "Modelo 303 (IVA)", "iva"]] },
      { etiqueta: "Ficheros", botones: [["👥", "Clientes / Proveedores", "terceros"]] },
    ],
  },
  {
    id: "inventario", label: "Inventario",
    grupos: [
      { etiqueta: "Inmovilizado", botones: [["🏭", "Fichas de activos", "activos"]] },
    ],
  },
  {
    id: "cierre", label: "Cierre",
    grupos: [
      { etiqueta: "Ejercicio", botones: [["🔒", "Cierre y apertura", "ejercicios"]] },
    ],
  },
  {
    id: "bancos", label: "Bancos",
    grupos: [
      { etiqueta: "Conciliación", botones: [["🏦", "Conciliación bancaria", "bancos"]] },
    ],
  },
  {
    id: "empresa", label: "Empresa",
    grupos: [
      { etiqueta: "Administración", botones: [["👥", "Usuarios", "usuarios"]] },
    ],
  },
  {
    id: "informes", label: "Impresión oficial",
    grupos: [
      { etiqueta: "Cuentas anuales", botones: [["🏦", "Balance de situación", "balance"], ["📈", "Pérdidas y ganancias", "pyg"]] },
      { etiqueta: "Libros", botones: [["📖", "Libro diario", "diario"], ["📚", "Libro mayor", "mayor"], ["⚖️", "Sumas y saldos", "sumas"]] },
      { etiqueta: "Impuestos", botones: [["🏛️", "Modelo 303 (IVA)", "iva"]] },
      { etiqueta: "Modelos AEAT", botones: [["🏛️", "Modelo 303", "aeat303"], ["📊", "Modelo 390", "aeat390"], ["🧾", "Modelo 347", "aeat347"]] },
    ],
  },
];

function pintarRibbon(tabActiva) {
  $("#ribbon-tabs").innerHTML = RIBBON.map(
    (t) => `<button data-tab="${t.id}" class="${t.id === tabActiva ? "activo" : ""}">${t.label}</button>`
  ).join("");
  const tab = RIBBON.find((t) => t.id === tabActiva);
  $("#ribbon-cuerpo").innerHTML = tab.grupos.map(
    (g) => `<div class="ribbon-grupo"><div class="ribbon-botones">${g.botones.map(
      ([icono, label, vista]) =>
        `<button class="ribbon-boton ${vista === vistaActual ? "activo" : ""}" data-vista="${vista}">
           <span class="icono">${icono}</span><span>${label}</span></button>`
    ).join("")}</div><div class="etiqueta">${g.etiqueta}</div></div>`
  ).join("");

  $$("#ribbon-tabs button").forEach((b) => (b.onclick = () => pintarRibbon(b.dataset.tab)));
  $$(".ribbon-boton").forEach((b) => (b.onclick = () => abrirVista(b.dataset.vista)));
}

function abrirVista(id) {
  vistaActual = id;
  $$(".ribbon-boton").forEach((b) => b.classList.toggle("activo", b.dataset.vista === id));
  vistas[id]().catch(fallo);
}

/* ---------- utilidades de interfaz ---------- */

function ventana(icono, titulo, cuerpo) {
  return `<div class="ventana"><div class="ventana-titulo"><span class="icono">${icono}</span>${titulo}</div>${cuerpo}</div>`;
}

// Selección de fila en una rejilla: devuelve () => id seleccionado y habilita botones.
function conSeleccion(idTabla, botones, alAbrir) {
  let sel = null;
  const tbody = $(`#${idTabla} tbody`);
  const actualizar = () => botones.forEach((b) => { const el = $(b); if (el) el.disabled = sel === null; });
  actualizar();
  if (tbody) {
    tbody.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-id]");
      if (!tr) return;
      $$("tr.sel", tbody).forEach((x) => x.classList.remove("sel"));
      tr.classList.add("sel");
      sel = tr.dataset.id;
      actualizar();
    });
    if (alAbrir) tbody.addEventListener("dblclick", (e) => {
      const tr = e.target.closest("tr[data-id]");
      if (tr) alAbrir(tr.dataset.id);
    });
  }
  return () => sel;
}

function tablaApuntes(apuntes) {
  return `<table class="grid"><thead>
    <tr><th>Id</th><th>Cuenta</th><th>Título</th><th>Concepto</th><th class="num">Debe</th><th class="num">Haber</th></tr></thead><tbody>
    ${apuntes.map((a) => `<tr><td>${a.id}</td><td>${esc(a.cuenta)}</td><td>${esc(a.cuenta_nombre)}</td><td>${esc(a.concepto)}</td>
      <td class="num">${a.debe ? eur(a.debe) : ""}</td><td class="num">${a.haber ? eur(a.haber) : ""}</td></tr>`).join("")}
  </tbody></table>`;
}

async function verAsiento(id) {
  const a = await api(`/asientos/${id}`);
  abrirModal(
    `Asiento ${a.numero}/${a.fecha.slice(0, 4)} — ${fecha_es(a.fecha)}`,
    `<p style="margin-bottom:8px">${esc(a.concepto)}</p>` + tablaApuntes(a.apuntes)
  );
}

const vistas = {};

/* ---------- Inicio: resumen ---------- */

vistas.inicio = async () => {
  const p = await api("/informes/panel");
  const clase = (v) => (v >= 0 ? "pos" : "neg");
  $("#area").innerHTML = ventana("📊", `Resumen de la empresa · ejercicio ${p.ejercicio}`, `
    <div class="tarjetas">
      <div class="tarjeta"><div class="etiqueta">Resultado del ejercicio</div>
        <div class="valor ${clase(p.resultado_ejercicio)}">${eur(p.resultado_ejercicio)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Ingresos</div><div class="valor">${eur(p.ingresos_ejercicio)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Gastos</div><div class="valor">${eur(p.gastos_ejercicio)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Tesorería (grupo 57)</div>
        <div class="valor ${clase(p.tesoreria)}">${eur(p.tesoreria)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Pendiente de cobro</div><div class="valor">${eur(p.pendiente_cobro)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Pendiente de pago</div><div class="valor">${eur(p.pendiente_pago)}</div></div>
      <div class="tarjeta"><div class="etiqueta">IVA ${p.iva_trimestre.trimestre}T</div>
        <div class="valor ${clase(-p.iva_trimestre.resultado)}">${eur(p.iva_trimestre.resultado)}</div></div>
      <div class="tarjeta"><div class="etiqueta">Asientos en el diario</div><div class="valor">${p.num_asientos}</div></div>
    </div>
    <p class="aviso">Datos en SQLite local. API REST en <a href="/docs" target="_blank">/docs</a> ·
      contexto para IA en <code>/api/v1/ia/contexto</code>.</p>`);
};

/* ---------- Introducción de asientos ---------- */

function filaEntrada() {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td style="width:120px"><input list="dl-cuentas" class="e-cuenta" placeholder="Cuenta"></td>
    <td style="width:220px" class="e-titulo" style="color:var(--suave)"></td>
    <td><input class="e-concepto" placeholder="Concepto"></td>
    <td style="width:120px"><input class="e-debe num" type="number" step="0.01" min="0"></td>
    <td style="width:120px"><input class="e-haber num" type="number" step="0.01" min="0"></td>`;
  $(".e-cuenta", tr).addEventListener("input", (e) => {
    $(".e-titulo", tr).textContent = cuentas.get(e.target.value.trim()) || "";
  });
  return tr;
}

function totalesEntrada() {
  let debe = 0, haber = 0;
  $$("#entrada-asientos tbody tr").forEach((tr) => {
    debe += parseFloat($(".e-debe", tr).value) || 0;
    haber += parseFloat($(".e-haber", tr).value) || 0;
  });
  const dif = Math.round((debe - haber) * 100) / 100;
  $("#e-tdebe").textContent = eur(debe);
  $("#e-thaber").textContent = eur(haber);
  const d = $("#e-descuadre");
  d.textContent = dif ? eur(dif) : "0,00 € ✓";
  d.className = "dato " + (dif ? "descuadre-mal" : "descuadre-ok");
}

vistas.nuevoAsiento = async () => {
  $("#area").innerHTML = ventana("📝", "Introducción de asientos", `
    <div class="toolbar">
      <label>Fecha<input type="date" id="e-fecha" value="${hoy()}"></label>
      <label>Concepto general<input id="e-conceptog" placeholder="Concepto del asiento" style="width:280px"></label>
      <span class="sep"></span>
      <button id="e-guardar">💾 Guardar asiento</button>
      <button id="e-limpiar">🧹 Limpiar</button>
      <span class="sep"></span>
      <button id="e-fila">➕ Añadir línea</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="entrada-asientos"><thead>
      <tr><th>Cuenta</th><th>Título de la cuenta</th><th>Concepto</th><th class="num">Debe</th><th class="num">Haber</th></tr>
    </thead><tbody></tbody></table></div>
    <div class="pie-ventana">
      <span>Total debe: <span class="dato" id="e-tdebe">0</span></span>
      <span>Total haber: <span class="dato" id="e-thaber">0</span></span>
      <span>Descuadre: <span class="dato" id="e-descuadre">0</span></span>
      <span class="aviso" style="margin-left:auto;padding:0">Intro salta al campo siguiente; se añaden líneas automáticamente.</span>
    </div>`);

  const tbody = $("#entrada-asientos tbody");
  tbody.append(filaEntrada(), filaEntrada());
  tbody.addEventListener("input", () => {
    const ultima = tbody.lastElementChild;
    if (ultima && $(".e-cuenta", ultima).value.trim()) tbody.append(filaEntrada());
    totalesEntrada();
  });
  tbody.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const inputs = $$("#entrada-asientos tbody input");
    const i = inputs.indexOf(e.target);
    if (i >= 0 && i + 1 < inputs.length) inputs[i + 1].focus();
  });
  totalesEntrada();

  $("#e-fila").onclick = () => tbody.append(filaEntrada());
  $("#e-limpiar").onclick = () => vistas.nuevoAsiento();
  $("#e-guardar").onclick = async () => {
    const apuntes = $$("#entrada-asientos tbody tr")
      .map((tr) => ({
        cuenta: $(".e-cuenta", tr).value.trim(),
        concepto: $(".e-concepto", tr).value.trim(),
        debe: parseFloat($(".e-debe", tr).value) || 0,
        haber: parseFloat($(".e-haber", tr).value) || 0,
      }))
      .filter((a) => a.cuenta);
    try {
      const a = await api("/asientos", {
        method: "POST",
        body: JSON.stringify({
          fecha: $("#e-fecha").value,
          concepto: $("#e-conceptog").value.trim() || "Asiento manual",
          apuntes,
        }),
      });
      toast(`Asiento ${a.numero}/${a.fecha.slice(0, 4)} guardado`);
      const fecha = $("#e-fecha").value;
      await vistas.nuevoAsiento();
      $("#e-fecha").value = fecha;
      $(".e-cuenta").focus();
    } catch (e) { fallo(e); }
  };
  $(".e-cuenta").focus();
};

/* ---------- Consulta de diario ---------- */

vistas.diario = async () => {
  $("#area").innerHTML = ventana("📖", "Consulta de diario", `
    <div class="toolbar">
      <label>Desde<input type="date" id="d-desde" value="${desdeEj()}"></label>
      <label>Hasta<input type="date" id="d-hasta" value="${hastaEj()}"></label>
      <label>Cuenta<input list="dl-cuentas" id="d-cuenta" placeholder="prefijo" style="width:110px"></label>
      <button id="d-filtrar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="d-nuevo">📝 Introducir</button>
      <button id="d-ver" disabled>👁 Ver asiento</button>
      <button id="d-borrar" disabled>🗑 Eliminar asiento</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-diario"><thead>
      <tr><th>Asiento</th><th>Fecha</th><th>Cuenta</th><th>Título</th><th>Concepto</th>
      <th class="num">Debe</th><th class="num">Haber</th></tr></thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="d-pie"></div>`);

  $("#d-nuevo").onclick = () => abrirVista("nuevoAsiento");
  $("#d-filtrar").onclick = () => cargarDiario();

  const seleccion = conSeleccion("grid-diario", ["#d-ver", "#d-borrar"], (id) => verAsiento(id).catch(fallo));
  $("#d-ver").onclick = () => verAsiento(seleccion()).catch(fallo);
  $("#d-borrar").onclick = async () => {
    if (!confirm("¿Eliminar el asiento seleccionado? Esta acción no se puede deshacer.")) return;
    try {
      await api(`/asientos/${seleccion()}`, { method: "DELETE" });
      toast("Asiento eliminado");
      cargarDiario();
    } catch (e) { fallo(e); }
  };
  await cargarDiario();
};

async function cargarDiario() {
  const p = new URLSearchParams({ limite: 500 });
  if ($("#d-desde").value) p.set("desde", $("#d-desde").value);
  if ($("#d-hasta").value) p.set("hasta", $("#d-hasta").value);
  if ($("#d-cuenta").value.trim()) p.set("cuenta", $("#d-cuenta").value.trim());
  const asientos = await api("/asientos?" + p);

  let debe = 0, haber = 0;
  const filas = [];
  for (const a of asientos) {
    a.apuntes.forEach((ap, i) => {
      debe += ap.debe; haber += ap.haber;
      filas.push(`<tr data-id="${a.id}">
        <td>${i === 0 ? `<b>${a.numero}/${a.fecha.slice(0, 4)}</b>` : ""}</td>
        <td>${i === 0 ? fecha_es(a.fecha) : ""}</td>
        <td>${esc(ap.cuenta)}</td><td>${esc(ap.cuenta_nombre)}</td><td>${esc(ap.concepto)}</td>
        <td class="num">${ap.debe ? eur(ap.debe) : ""}</td><td class="num">${ap.haber ? eur(ap.haber) : ""}</td></tr>`);
    });
  }
  $("#grid-diario tbody").innerHTML = filas.join("") ||
    `<tr><td colspan="7" class="aviso">Sin asientos en el periodo.</td></tr>`;
  $("#d-pie").innerHTML = `<span>Asientos: <span class="dato">${asientos.length}</span></span>
    <span>Total debe: <span class="dato">${eur(debe)}</span></span>
    <span>Total haber: <span class="dato">${eur(haber)}</span></span>`;
}

/* ---------- Extracto de mayor ---------- */

vistas.mayor = async () => {
  $("#area").innerHTML = ventana("📚", "Extracto de mayor", `
    <div class="toolbar">
      <label>Cuenta o prefijo<input list="dl-cuentas" id="m-cuenta" placeholder="572" style="width:130px"></label>
      <label>Desde<input type="date" id="m-desde" value="${desdeEj()}"></label>
      <label>Hasta<input type="date" id="m-hasta" value="${hastaEj()}"></label>
      <button id="m-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="m-pdf">📄 PDF</button>
      <button id="m-excel">📊 Excel</button>
    </div>
    <div id="m-salida"><p class="aviso">Indica una cuenta y pulsa Consultar.</p></div>`);

  const parametrosMayor = () => {
    const cuenta = $("#m-cuenta").value.trim();
    const p = new URLSearchParams({ cuenta });
    if ($("#m-desde").value) p.set("desde", $("#m-desde").value);
    if ($("#m-hasta").value) p.set("hasta", $("#m-hasta").value);
    return p;
  };
  $("#m-pdf").onclick = () => window.open("/api/v1/informes/mayor?" + parametrosMayor() + "&formato=pdf", "_blank");
  $("#m-excel").onclick = () => window.open("/api/v1/informes/mayor?" + parametrosMayor() + "&formato=excel", "_blank");

  $("#m-generar").onclick = async () => {
    const cuenta = $("#m-cuenta").value.trim();
    if (!cuenta) return;
    const p = parametrosMayor();
    try {
      const m = await api("/informes/mayor?" + p);
      $("#m-salida").innerHTML = `
        <div class="grid-wrap"><table class="grid"><thead>
          <tr><th>Fecha</th><th>Asiento</th><th>Cuenta</th><th>Concepto</th>
          <th class="num">Debe</th><th class="num">Haber</th><th class="num">Saldo</th></tr></thead><tbody>
          ${m.movimientos.map((x) => `<tr><td>${fecha_es(x.fecha)}</td><td>${x.asiento}</td><td>${esc(x.cuenta)}</td>
            <td>${esc(x.concepto)}</td><td class="num">${x.debe ? eur(x.debe) : ""}</td>
            <td class="num">${x.haber ? eur(x.haber) : ""}</td><td class="num">${eur(x.saldo)}</td></tr>`).join("") ||
            `<tr><td colspan="7" class="aviso">Sin movimientos.</td></tr>`}
        </tbody></table></div>
        <div class="pie-ventana">
          <span>${esc(m.cuenta)} ${esc(m.nombre)}</span>
          <span>Debe: <span class="dato">${eur(m.total_debe)}</span></span>
          <span>Haber: <span class="dato">${eur(m.total_haber)}</span></span>
          <span>Saldo: <span class="dato ${m.saldo >= 0 ? "" : "neg"}">${eur(m.saldo)}</span></span>
        </div>`;
    } catch (e) { fallo(e); }
  };
};

/* ---------- Sumas y saldos ---------- */

vistas.sumas = async () => {
  $("#area").innerHTML = ventana("⚖️", "Balance de sumas y saldos", `
    <div class="toolbar">
      <label>Desde<input type="date" id="s-desde" value="${desdeEj()}"></label>
      <label>Hasta<input type="date" id="s-hasta" value="${hastaEj()}"></label>
      <button id="s-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="s-pdf">📄 PDF</button>
      <button id="s-excel">📊 Excel</button>
    </div>
    <div id="s-salida"></div>`);

  const parametrosSumas = () => {
    const p = new URLSearchParams();
    if ($("#s-desde").value) p.set("desde", $("#s-desde").value);
    if ($("#s-hasta").value) p.set("hasta", $("#s-hasta").value);
    return p;
  };
  $("#s-pdf").onclick = () => window.open("/api/v1/informes/sumas-saldos?" + parametrosSumas() + "&formato=pdf", "_blank");
  $("#s-excel").onclick = () => window.open("/api/v1/informes/sumas-saldos?" + parametrosSumas() + "&formato=excel", "_blank");

  const generar = async () => {
    const p = parametrosSumas();
    const s = await api("/informes/sumas-saldos?" + p);
    $("#s-salida").innerHTML = `
      <div class="grid-wrap"><table class="grid"><thead>
        <tr><th>Cuenta</th><th>Título</th><th class="num">Debe</th><th class="num">Haber</th>
        <th class="num">Saldo deudor</th><th class="num">Saldo acreedor</th></tr></thead><tbody>
        ${s.filas.map((f) => `<tr><td>${esc(f.cuenta)}</td><td>${esc(f.nombre)}</td>
          <td class="num">${eur(f.debe)}</td><td class="num">${eur(f.haber)}</td>
          <td class="num">${f.saldo_deudor ? eur(f.saldo_deudor) : ""}</td>
          <td class="num">${f.saldo_acreedor ? eur(f.saldo_acreedor) : ""}</td></tr>`).join("")}
        <tr class="total-fila"><td colspan="2">TOTALES ${s.cuadrado ? "✓" : "⚠ DESCUADRE"}</td>
          <td class="num">${eur(s.total_debe)}</td><td class="num">${eur(s.total_haber)}</td><td></td><td></td></tr>
      </tbody></table></div>`;
  };
  $("#s-generar").onclick = () => generar().catch(fallo);
  await generar();
};

/* ---------- P.G.C. ---------- */

vistas.pgc = async () => {
  $("#area").innerHTML = ventana("🗂️", "Plan General Contable — maestro de cuentas", `
    <div class="toolbar">
      <label>Buscar<input id="c-q" placeholder="código o título" style="width:180px"></label>
      <button id="c-buscar">🔍 Buscar</button>
      <span class="sep"></span>
      <button id="c-nueva">➕ Nueva cuenta</button>
      <button id="c-mayor" disabled>📚 Extracto</button>
      <button id="c-borrar" disabled>🗑 Eliminar</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-cuentas"><thead>
      <tr><th style="width:120px">Cuenta</th><th>Título</th></tr></thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="c-pie"></div>`);

  const cargar = async () => {
    const q = $("#c-q").value.trim();
    const lista = await api("/cuentas" + (q ? "?q=" + encodeURIComponent(q) : ""));
    $("#grid-cuentas tbody").innerHTML = lista.map(
      (c) => `<tr data-id="${esc(c.codigo)}"><td>${esc(c.codigo)}</td><td>${esc(c.nombre)}</td></tr>`
    ).join("");
    $("#c-pie").innerHTML = `<span>Cuentas: <span class="dato">${lista.length}</span></span>`;
  };
  const seleccion = conSeleccion("grid-cuentas", ["#c-mayor", "#c-borrar"]);

  $("#c-buscar").onclick = () => cargar().catch(fallo);
  $("#c-q").onkeydown = (e) => { if (e.key === "Enter") cargar().catch(fallo); };
  $("#c-mayor").onclick = () => { $; abrirVista("mayor"); setTimeout(() => { $("#m-cuenta").value = seleccion() ?? ""; $("#m-generar").click(); }); };
  $("#c-borrar").onclick = async () => {
    if (!confirm(`¿Eliminar la cuenta ${seleccion()}?`)) return;
    try {
      await api(`/cuentas/${seleccion()}`, { method: "DELETE" });
      toast("Cuenta eliminada"); await recargarCuentas(); cargar();
    } catch (e) { fallo(e); }
  };
  $("#c-nueva").onclick = () => {
    abrirModal("Nueva cuenta", `
      <form class="formulario" id="form-cuenta">
        <label>Código<input id="fc-codigo" required pattern="\\d+" maxlength="10" placeholder="6290001"></label>
        <label class="ancho">Título<input id="fc-nombre" required maxlength="120"></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Crear</button>
        </div>
      </form>`);
    $("#form-cuenta").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/cuentas", { method: "POST", body: JSON.stringify({ codigo: $("#fc-codigo").value.trim(), nombre: $("#fc-nombre").value.trim() }) });
        toast("Cuenta creada"); cerrarModal(); await recargarCuentas(); cargar();
      } catch (err) { fallo(err); }
    };
  };
  await cargar();
};

/* ---------- Terceros ---------- */

vistas.terceros = async () => {
  $("#area").innerHTML = ventana("👥", "Clientes y proveedores", `
    <div class="toolbar">
      <button id="t-nuevo">➕ Nuevo</button>
      <button id="t-editar" disabled>✏️ Editar</button>
      <button id="t-borrar" disabled>🗑 Eliminar</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-terceros"><thead>
      <tr><th>Nombre</th><th>NIF</th><th>Tipo</th><th>Subcuentas</th><th>Teléfono</th><th>Email</th><th>Dirección</th></tr>
    </thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="t-pie"></div>`);

  let lista = [];
  const cargar = async () => {
    lista = await api("/terceros");
    $("#grid-terceros tbody").innerHTML = lista.map((t) => `<tr data-id="${t.id}">
      <td><b>${esc(t.nombre)}</b></td><td>${esc(t.nif)}</td><td>${esc(t.tipo)}</td>
      <td>${[t.cuenta_cliente, t.cuenta_proveedor].filter(Boolean).map(esc).join(" · ") || "—"}</td>
      <td>${esc(t.telefono)}</td><td>${esc(t.email)}</td><td>${esc(t.direccion)}</td></tr>`).join("");
    $("#t-pie").innerHTML = `<span>Terceros: <span class="dato">${lista.length}</span></span>`;
  };
  const seleccion = conSeleccion("grid-terceros", ["#t-editar", "#t-borrar"], (id) => formulario(lista.find((x) => x.id == id)));

  const formulario = (t) => {
    abrirModal(t ? `Editar tercero — ${t.nombre}` : "Nuevo tercero", `
      <form class="formulario" id="form-tercero">
        <label>Tipo<select id="ft-tipo">
          <option value="cliente">Cliente</option><option value="proveedor">Proveedor</option><option value="ambos">Ambos</option>
        </select></label>
        <label>NIF<input id="ft-nif" required maxlength="20"></label>
        <label class="ancho">Nombre / razón social<input id="ft-nombre" required maxlength="150"></label>
        <label>Teléfono<input id="ft-telefono" maxlength="30"></label>
        <label>Email<input id="ft-email" type="email" maxlength="100"></label>
        <label class="ancho">Dirección<input id="ft-direccion" maxlength="200"></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">${t ? "Guardar cambios" : "Crear"}</button>
        </div>
      </form>`);
    if (t) {
      $("#ft-tipo").value = t.tipo; $("#ft-nif").value = t.nif; $("#ft-nombre").value = t.nombre;
      $("#ft-telefono").value = t.telefono || ""; $("#ft-email").value = t.email || "";
      $("#ft-direccion").value = t.direccion || "";
    }
    $("#form-tercero").onsubmit = async (e) => {
      e.preventDefault();
      const cuerpo = {
        tipo: $("#ft-tipo").value, nif: $("#ft-nif").value.trim(), nombre: $("#ft-nombre").value.trim(),
        telefono: $("#ft-telefono").value.trim(), email: $("#ft-email").value.trim(), direccion: $("#ft-direccion").value.trim(),
      };
      try {
        await api(t ? `/terceros/${t.id}` : "/terceros", { method: t ? "PUT" : "POST", body: JSON.stringify(cuerpo) });
        toast(t ? "Tercero actualizado" : "Tercero creado");
        cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };

  $("#t-nuevo").onclick = () => formulario(null);
  $("#t-editar").onclick = () => formulario(lista.find((x) => x.id == seleccion()));
  $("#t-borrar").onclick = async () => {
    if (!confirm("¿Eliminar el tercero seleccionado?")) return;
    try { await api(`/terceros/${seleccion()}`, { method: "DELETE" }); toast("Tercero eliminado"); cargar(); }
    catch (e) { fallo(e); }
  };
  await cargar();
};

/* ---------- Facturas ---------- */

vistas.emitidas = () => vistaFacturas("emitida");
vistas.recibidas = () => vistaFacturas("recibida");

async function vistaFacturas(tipo) {
  const esEmitida = tipo === "emitida";
  $("#area").innerHTML = ventana(esEmitida ? "🧾" : "📄",
    esEmitida ? "Facturas emitidas (IVA repercutido)" : "Facturas recibidas (IVA soportado)", `
    <div class="toolbar">
      <button id="f-nueva">➕ Nueva factura</button>
      <button id="f-liquidar" disabled>💶 ${esEmitida ? "Cobrar" : "Pagar"}</button>
      <button id="f-asiento" disabled>👁 Ver asiento</button>
      <button id="f-borrar" disabled>🗑 Eliminar</button>
      <span class="sep"></span>
      <label>Estado<select id="f-estado"><option value="">Todas</option>
        <option value="pendiente">Pendientes</option><option value="pagada">Liquidadas</option></select></label>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-facturas"><thead>
      <tr><th>Número</th><th>Fecha</th><th>${esEmitida ? "Cliente" : "Proveedor"}</th>
      <th class="num">Base</th><th class="num">IVA</th><th class="num">Retención</th>
      <th class="num">Total</th><th>Estado</th></tr></thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="f-pie"></div>`);

  let lista = [];
  const cargar = async () => {
    const p = new URLSearchParams({ tipo, desde: desdeEj(), hasta: hastaEj() });
    if ($("#f-estado").value) p.set("estado", $("#f-estado").value);
    lista = await api("/facturas?" + p);
    $("#grid-facturas tbody").innerHTML = lista.map((f) => `<tr data-id="${f.id}">
      <td><b>${esc(f.numero)}</b></td><td>${fecha_es(f.fecha)}</td><td>${esc(f.tercero_nombre)}</td>
      <td class="num">${eur(f.base_total)}</td><td class="num">${eur(f.cuota_iva)}</td>
      <td class="num">${f.retencion_importe ? eur(f.retencion_importe) : ""}</td>
      <td class="num"><b>${eur(f.total)}</b></td>
      <td><span class="pill ${f.estado}">${f.estado === "pagada" ? "liquidada" : "pendiente"}</span></td></tr>`).join("") ||
      `<tr><td colspan="8" class="aviso">Sin facturas ${tipo}s en ${ejercicio}.</td></tr>`;
    $("#f-pie").innerHTML = `<span>Facturas: <span class="dato">${lista.length}</span></span>
      <span>Base: <span class="dato">${eur(lista.reduce((s, f) => s + f.base_total, 0))}</span></span>
      <span>IVA: <span class="dato">${eur(lista.reduce((s, f) => s + f.cuota_iva, 0))}</span></span>
      <span>Total: <span class="dato">${eur(lista.reduce((s, f) => s + f.total, 0))}</span></span>`;
  };
  const seleccion = conSeleccion("grid-facturas", ["#f-liquidar", "#f-asiento", "#f-borrar"],
    (id) => { const f = lista.find((x) => x.id == id); if (f) verAsiento(f.asiento_id).catch(fallo); });

  $("#f-estado").onchange = () => cargar().catch(fallo);
  $("#f-asiento").onclick = () => {
    const f = lista.find((x) => x.id == seleccion());
    verAsiento(f.asiento_id).catch(fallo);
  };
  $("#f-borrar").onclick = async () => {
    if (!confirm("¿Eliminar la factura y sus asientos asociados?")) return;
    try { await api(`/facturas/${seleccion()}`, { method: "DELETE" }); toast("Factura eliminada"); cargar(); }
    catch (e) { fallo(e); }
  };
  $("#f-liquidar").onclick = () => {
    const f = lista.find((x) => x.id == seleccion());
    if (!f) return;
    if (f.estado === "pagada") { toast("La factura ya está liquidada", true); return; }
    abrirModal(`${esEmitida ? "Cobro" : "Pago"} de la factura ${f.numero}`, `
      <form class="formulario" id="form-liquidar">
        <label>Fecha<input type="date" id="fl-fecha" value="${hoy()}" required></label>
        <label>Cuenta de tesorería<input list="dl-cuentas" id="fl-cuenta" value="572"></label>
        <p class="ancho aviso" style="padding:0">Importe: <b>${eur(f.total - f.retencion_importe)}</b> (total − retención)</p>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">${esEmitida ? "Registrar cobro" : "Registrar pago"}</button>
        </div>
      </form>`);
    $("#form-liquidar").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/facturas/${f.id}/liquidar`, {
          method: "POST",
          body: JSON.stringify({ fecha: $("#fl-fecha").value, cuenta_tesoreria: $("#fl-cuenta").value.trim() || "572" }),
        });
        toast("Factura liquidada"); cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };
  $("#f-nueva").onclick = () => nuevaFactura(tipo, cargar);
  await cargar();
}

function filaLineaFactura() {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input class="l-desc" placeholder="Descripción"></td>
    <td style="width:120px"><input class="l-base num" type="number" step="0.01" min="0"></td>
    <td style="width:90px"><select class="l-iva">
      <option value="21">21 %</option><option value="10">10 %</option><option value="4">4 %</option><option value="0">0 %</option>
    </select></td>
    <td style="width:40px;text-align:center"><button type="button" class="secundario l-quitar">✕</button></td>`;
  $(".l-quitar", tr).onclick = () => tr.remove();
  return tr;
}

async function nuevaFactura(tipo, alGuardar) {
  const esEmitida = tipo === "emitida";
  const filtro = esEmitida ? "cliente" : "proveedor";
  const terceros = (await api("/terceros")).filter((t) => t.tipo === filtro || t.tipo === "ambos");
  if (!terceros.length) {
    toast(`Primero crea un ${filtro} en Clientes / Proveedores`, true);
    return;
  }
  abrirModal(`Nueva factura ${tipo}`, `
    <form id="form-factura">
      <div class="formulario">
        <label>Número<input id="ff-numero" required maxlength="30" placeholder="F-${ejercicio}-001"></label>
        <label>Fecha<input type="date" id="ff-fecha" value="${hoy()}" required></label>
        <label class="ancho">${esEmitida ? "Cliente" : "Proveedor"}<select id="ff-tercero">
          ${terceros.map((t) => `<option value="${t.id}">${esc(t.nombre)} (${esc(t.nif)})</option>`).join("")}
        </select></label>
        <label>Cuenta ${esEmitida ? "de ingreso" : "de gasto"}<input list="dl-cuentas" id="ff-contrapartida" value="${esEmitida ? "700" : "600"}"></label>
        <label>Retención IRPF %<input id="ff-retencion" class="num" type="number" step="0.01" min="0" max="100" value="0"></label>
      </div>
      <table class="grid" id="ff-lineas"><thead>
        <tr><th>Concepto</th><th class="num">Base imponible</th><th>IVA</th><th></th></tr></thead><tbody></tbody></table>
      <div style="display:flex;gap:8px;align-items:center;padding:8px 0">
        <button type="button" class="secundario" id="ff-addlinea">➕ Línea</button>
        <span style="margin-left:auto" id="ff-totales"></span>
      </div>
      <div class="botones-form">
        <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
        <button type="submit" class="principal">Registrar y contabilizar</button>
      </div>
    </form>`);

  const tbody = $("#ff-lineas tbody");
  tbody.append(filaLineaFactura());
  const totales = () => {
    let base = 0, iva = 0;
    $$("#ff-lineas tbody tr").forEach((tr) => {
      const b = parseFloat($(".l-base", tr).value) || 0;
      base += b; iva += b * parseFloat($(".l-iva", tr).value) / 100;
    });
    const ret = base * (parseFloat($("#ff-retencion").value) || 0) / 100;
    $("#ff-totales").innerHTML =
      `Base <b>${eur(base)}</b> · IVA <b>${eur(iva)}</b>${ret ? ` · Retención <b>${eur(ret)}</b>` : ""} · Total <b>${eur(base + iva)}</b>`;
  };
  $("#form-factura").addEventListener("input", totales);
  totales();
  $("#ff-addlinea").onclick = () => tbody.append(filaLineaFactura());

  $("#form-factura").onsubmit = async (e) => {
    e.preventDefault();
    const lineas = $$("#ff-lineas tbody tr")
      .map((tr) => ({
        descripcion: $(".l-desc", tr).value.trim(),
        base: parseFloat($(".l-base", tr).value) || 0,
        tipo_iva: parseFloat($(".l-iva", tr).value),
      }))
      .filter((l) => l.descripcion && l.base > 0);
    try {
      await api("/facturas", {
        method: "POST",
        body: JSON.stringify({
          tipo, numero: $("#ff-numero").value.trim(), fecha: $("#ff-fecha").value,
          tercero_id: parseInt($("#ff-tercero").value, 10),
          cuenta_contrapartida: $("#ff-contrapartida").value.trim() || null,
          retencion_pct: parseFloat($("#ff-retencion").value) || 0,
          lineas,
        }),
      });
      toast("Factura registrada y contabilizada");
      cerrarModal();
      await recargarCuentas(); // puede haber creado la subcuenta del tercero
      alGuardar();
    } catch (err) { fallo(err); }
  };
}

/* ---------- Inmovilizado ---------- */

vistas.activos = async () => {
  $("#area").innerHTML = ventana("🏭", "Inventario — fichas de inmovilizado", `
    <div class="toolbar">
      <button id="a-nueva">➕ Nueva ficha</button>
      <button id="a-amortizar" disabled>📉 Amortizar ejercicio</button>
      <button id="a-dotaciones" disabled>📋 Dotaciones</button>
      <button id="a-borrar" disabled>🗑 Eliminar</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-activos"><thead>
      <tr><th>Activo</th><th>Adquisición</th><th>Cuenta</th><th class="num">Valor</th>
      <th class="num">Amortizado</th><th class="num">Valor neto</th><th>Vida útil</th></tr></thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="a-pie"></div>`);

  let lista = [];
  const cargar = async () => {
    lista = await api("/activos");
    $("#grid-activos tbody").innerHTML = lista.map((a) => `<tr data-id="${a.id}">
      <td><b>${esc(a.nombre)}</b></td><td>${fecha_es(a.fecha_adquisicion)}</td><td>${esc(a.cuenta_activo)}</td>
      <td class="num">${eur(a.valor)}</td><td class="num">${eur(a.amortizado)}</td>
      <td class="num"><b>${eur(a.valor_neto)}</b></td><td>${a.vida_util_anios} años</td></tr>`).join("") ||
      `<tr><td colspan="7" class="aviso">Sin activos registrados.</td></tr>`;
    $("#a-pie").innerHTML = `<span>Activos: <span class="dato">${lista.length}</span></span>
      <span>Valor neto total: <span class="dato">${eur(lista.reduce((s, a) => s + a.valor_neto, 0))}</span></span>`;
  };
  const seleccion = conSeleccion("grid-activos", ["#a-amortizar", "#a-dotaciones", "#a-borrar"]);

  $("#a-nueva").onclick = () => {
    abrirModal("Nueva ficha de inmovilizado", `
      <form class="formulario" id="form-activo">
        <label class="ancho">Descripción<input id="fa-nombre" required maxlength="150"></label>
        <label>Fecha de adquisición<input type="date" id="fa-fecha" value="${hoy()}" required></label>
        <label>Valor de adquisición €<input id="fa-valor" class="num" type="number" step="0.01" min="0.01" required></label>
        <label>Valor residual €<input id="fa-residual" class="num" type="number" step="0.01" min="0" value="0"></label>
        <label>Vida útil (años)<input id="fa-vida" class="num" type="number" min="1" max="100" value="5"></label>
        <label>Cuenta del activo<input list="dl-cuentas" id="fa-cta" value="213"></label>
        <p class="ancho aviso" style="padding:0">La compra se contabiliza aparte (factura recibida con la cuenta del activo
        como contrapartida). La dotación anual genera el asiento 681 a 281 a 31/12.</p>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Dar de alta</button>
        </div>
      </form>`);
    $("#form-activo").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/activos", {
          method: "POST",
          body: JSON.stringify({
            nombre: $("#fa-nombre").value.trim(), fecha_adquisicion: $("#fa-fecha").value,
            valor: parseFloat($("#fa-valor").value), valor_residual: parseFloat($("#fa-residual").value) || 0,
            vida_util_anios: parseInt($("#fa-vida").value, 10), cuenta_activo: $("#fa-cta").value.trim() || "213",
          }),
        });
        toast("Activo dado de alta"); cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };

  $("#a-amortizar").onclick = async () => {
    const anio = prompt("Ejercicio a dotar:", String(ejercicio));
    if (!anio) return;
    try {
      await api(`/activos/${seleccion()}/amortizar`, { method: "POST", body: JSON.stringify({ ejercicio: parseInt(anio, 10) }) });
      toast(`Dotación de ${anio} contabilizada (681 a 281)`); cargar();
    } catch (e) { fallo(e); }
  };

  $("#a-dotaciones").onclick = () => {
    const a = lista.find((x) => x.id == seleccion());
    abrirModal(`Dotaciones — ${a.nombre}`, `
      <table class="grid"><thead><tr><th>Ejercicio</th><th class="num">Importe</th><th>Asiento</th><th></th></tr></thead><tbody>
      ${a.amortizaciones.map((m) => `<tr><td>${m.ejercicio}</td><td class="num">${eur(m.importe)}</td>
        <td><a href="#" onclick="verAsientoGlobal(${m.asiento_id});return false">ver</a></td>
        <td><button class="secundario" onclick="eliminarDotacionGlobal(${a.id},${m.ejercicio})">🗑</button></td></tr>`).join("") ||
        `<tr><td colspan="4" class="aviso">Sin dotaciones.</td></tr>`}
      </tbody></table>`);
  };

  window.verAsientoGlobal = (id) => verAsiento(id).catch(fallo);
  window.eliminarDotacionGlobal = async (activoId, anio) => {
    if (!confirm(`¿Eliminar la dotación de ${anio} y su asiento?`)) return;
    try {
      await api(`/activos/${activoId}/amortizaciones/${anio}`, { method: "DELETE" });
      toast("Dotación eliminada"); cerrarModal(); cargar();
    } catch (e) { fallo(e); }
  };

  $("#a-borrar").onclick = async () => {
    if (!confirm("¿Eliminar la ficha del activo?")) return;
    try { await api(`/activos/${seleccion()}`, { method: "DELETE" }); toast("Activo eliminado"); cargar(); }
    catch (e) { fallo(e); }
  };
  await cargar();
};

/* ---------- Pérdidas y ganancias ---------- */

vistas.pyg = async () => {
  $("#area").innerHTML = ventana("📈", "Cuenta de pérdidas y ganancias", `
    <div class="toolbar">
      <label>Desde<input type="date" id="p-desde" value="${desdeEj()}"></label>
      <label>Hasta<input type="date" id="p-hasta" value="${hastaEj()}"></label>
      <button id="p-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="p-pdf">📄 PDF</button>
      <button id="p-excel">📊 Excel</button>
    </div>
    <div id="p-salida"></div>`);

  const parametrosPyg = () => `desde=${$("#p-desde").value}&hasta=${$("#p-hasta").value}`;
  $("#p-pdf").onclick = () => window.open(`/api/v1/informes/pyg?${parametrosPyg()}&formato=pdf`, "_blank");
  $("#p-excel").onclick = () => window.open(`/api/v1/informes/pyg?${parametrosPyg()}&formato=excel`, "_blank");

  const generar = async () => {
    const p = await api(`/informes/pyg?${parametrosPyg()}`);
    const filas = (titulo, arr, total) => `
      <tr class="grupo-fila"><td colspan="3">${titulo}</td></tr>
      ${arr.map((f) => `<tr><td style="width:110px">${esc(f.cuenta)}</td><td>${esc(f.nombre)}</td>
        <td class="num" style="width:140px">${eur(f.importe)}</td></tr>`).join("")}
      <tr class="total-fila"><td colspan="2">Total ${titulo.toLowerCase()}</td><td class="num">${eur(total)}</td></tr>`;
    $("#p-salida").innerHTML = `
      <div class="grid-wrap"><table class="grid"><tbody>
        ${filas("INGRESOS (grupo 7)", p.ingresos, p.total_ingresos)}
        ${filas("GASTOS (grupo 6)", p.gastos, p.total_gastos)}
      </tbody></table></div>
      <div class="pie-ventana"><span>RESULTADO:
        <span class="dato ${p.resultado >= 0 ? "pos" : "neg"}">${eur(p.resultado)}</span>
        ${p.resultado >= 0 ? "(beneficio)" : "(pérdida)"}</span></div>`;
  };
  $("#p-generar").onclick = () => generar().catch(fallo);
  await generar();
};

/* ---------- Balance de situación ---------- */

vistas.balance = async () => {
  $("#area").innerHTML = ventana("🏦", "Balance de situación", `
    <div class="toolbar">
      <label>A fecha<input type="date" id="b-hasta" value="${hastaEj()}"></label>
      <button id="b-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="b-pdf">📄 PDF</button>
      <button id="b-excel">📊 Excel</button>
    </div>
    <div id="b-salida"></div>`);

  $("#b-pdf").onclick = () => window.open("/api/v1/informes/balance?hasta=" + $("#b-hasta").value + "&formato=pdf", "_blank");
  $("#b-excel").onclick = () => window.open("/api/v1/informes/balance?hasta=" + $("#b-hasta").value + "&formato=excel", "_blank");

  const generar = async () => {
    const b = await api("/informes/balance?hasta=" + $("#b-hasta").value);
    const lado = (titulo, secciones, total) => `
      <tr class="grupo-fila"><td colspan="3">${titulo}</td></tr>
      ${Object.entries(secciones).map(([nombre, filas]) => `
        <tr><td colspan="3" style="font-weight:600;background:#f6f2ee">${esc(nombre)}</td></tr>
        ${filas.map((f) => `<tr><td style="width:110px">${esc(f.cuenta)}</td><td>${esc(f.nombre)}</td>
          <td class="num" style="width:140px">${eur(f.importe)}</td></tr>`).join("")}`).join("")}
      <tr class="total-fila"><td colspan="2">TOTAL ${titulo}</td><td class="num">${eur(total)}</td></tr>`;
    $("#b-salida").innerHTML = `
      <div class="grid-wrap"><table class="grid"><tbody>
        ${lado("ACTIVO", b.activo, b.total_activo)}
        ${lado("PATRIMONIO NETO Y PASIVO", b.pasivo, b.total_pasivo)}
      </tbody></table></div>
      <div class="pie-ventana">
        <span>${b.cuadrado ? "✓ El balance cuadra" : "⚠ El balance NO cuadra"}</span>
        <span class="aviso" style="padding:0">Estructura oficial del balance de situación abreviado (PGC).</span>
      </div>`;
  };
  $("#b-generar").onclick = () => generar().catch(fallo);
  await generar();
};

/* ---------- IVA (modelo 303) ---------- */

vistas.iva = async () => {
  const triActual = Math.floor(new Date().getMonth() / 3) + 1;
  $("#area").innerHTML = ventana("🏛️", "Resumen de IVA — estilo modelo 303", `
    <div class="toolbar">
      <label>Ejercicio<input id="v-ejercicio" class="num" type="number" value="${ejercicio}" style="width:80px"></label>
      <label>Trimestre<select id="v-trimestre">
        ${[1, 2, 3, 4].map((t) => `<option value="${t}" ${t === triActual ? "selected" : ""}>${t}T</option>`).join("")}
      </select></label>
      <button id="v-generar">🔍 Consultar</button>
    </div>
    <div id="v-salida"></div>`);
  const generar = async () => {
    const v = await api(`/informes/iva?ejercicio=${$("#v-ejercicio").value}&trimestre=${$("#v-trimestre").value}`);
    const bloque = (titulo, d) => `
      <tr class="grupo-fila"><td colspan="3">${titulo}</td></tr>
      ${d.desglose.map((f) => `<tr><td style="width:110px">${f.tipo_iva} %</td>
        <td class="num">${eur(f.base)}</td><td class="num" style="width:140px">${eur(f.cuota)}</td></tr>`).join("") ||
        `<tr><td colspan="3" class="aviso">Sin facturas.</td></tr>`}
      <tr class="total-fila"><td>Total</td><td class="num">${eur(d.base)}</td><td class="num">${eur(d.cuota)}</td></tr>`;
    $("#v-salida").innerHTML = `
      <p class="aviso">Periodo: ${fecha_es(v.desde)} a ${fecha_es(v.hasta)} · calculado a partir de las facturas registradas.</p>
      <div class="grid-wrap"><table class="grid">
        <thead><tr><th>Tipo</th><th class="num">Base imponible</th><th class="num">Cuota</th></tr></thead><tbody>
        ${bloque("IVA REPERCUTIDO (facturas emitidas)", v.repercutido)}
        ${bloque("IVA SOPORTADO (facturas recibidas)", v.soportado)}
      </tbody></table></div>
      <div class="pie-ventana"><span>Resultado:
        <span class="dato ${v.resultado > 0 ? "neg" : "pos"}">${eur(v.resultado)}</span> ${v.sentido}</span></div>`;
  };
  $("#v-generar").onclick = () => generar().catch(fallo);
  await generar();
};

/* ---------- Cierre y apertura de ejercicio ---------- */

vistas.ejercicios = async () => {
  $("#area").innerHTML = ventana("🔒", "Cierre y apertura de ejercicio", `
    <div class="toolbar">
      <button id="ej-cerrar" disabled>🔒 Cerrar ejercicio</button>
      <button id="ej-abrir" disabled>🔓 Abrir ejercicio</button>
      <span class="sep"></span>
      <button id="ej-deshacer-cierre" disabled>↩️ Deshacer cierre</button>
      <button id="ej-deshacer-apertura" disabled>↩️ Deshacer apertura</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-ejercicios"><thead>
      <tr><th>Año</th><th>Abierto</th><th>Cerrado</th><th>Fecha apertura</th><th>Fecha cierre</th>
      <th class="num">Resultado</th></tr></thead><tbody></tbody></table></div>
    <p class="aviso">La regularización salda las cuentas de gastos e ingresos (grupos 6 y 7) contra la 129 ·
      el cierre salda el resto de cuentas patrimoniales · la apertura del ejercicio siguiente reabre esos saldos.</p>`);

  let lista = [];
  function actualizarBotones() {
    const anio = seleccion();
    const e = lista.find((x) => String(x.anio) === String(anio));
    $("#ej-cerrar").disabled = !e || e.cerrado;
    $("#ej-abrir").disabled = !e || e.abierto;
    $("#ej-deshacer-cierre").disabled = !e || !e.cerrado;
    $("#ej-deshacer-apertura").disabled = !e || !e.abierto;
  }

  const cargar = async () => {
    lista = await api("/ejercicios");
    $("#grid-ejercicios tbody").innerHTML = lista.map((e) => `<tr data-id="${e.anio}">
      <td><b>${e.anio}</b></td><td>${e.abierto ? "✓" : ""}</td><td>${e.cerrado ? "✓" : ""}</td>
      <td>${fecha_es(e.fecha_apertura)}</td><td>${fecha_es(e.fecha_cierre)}</td>
      <td class="num">${e.cerrado
        ? eur(e.resultado)
        : e.resultado_previsto != null ? `${eur(e.resultado_previsto)} (previsto)` : ""}</td>
      </tr>`).join("") || `<tr><td colspan="6" class="aviso">Sin ejercicios con movimientos.</td></tr>`;
    actualizarBotones();
  };

  const seleccion = conSeleccion("grid-ejercicios",
    ["#ej-cerrar", "#ej-abrir", "#ej-deshacer-cierre", "#ej-deshacer-apertura"]);
  $("#grid-ejercicios tbody").addEventListener("click", actualizarBotones);

  $("#ej-cerrar").onclick = async () => {
    const anio = seleccion();
    if (!confirm(`¿Cerrar el ejercicio ${anio}? Se generarán los asientos de regularización y cierre.`)) return;
    try { await api(`/ejercicios/${anio}/cerrar`, { method: "POST" }); toast(`Ejercicio ${anio} cerrado`); await cargar(); }
    catch (e) { fallo(e); }
  };
  $("#ej-abrir").onclick = async () => {
    const anio = seleccion();
    try { await api(`/ejercicios/${anio}/abrir`, { method: "POST" }); toast(`Ejercicio ${anio} abierto`); await cargar(); }
    catch (e) { fallo(e); }
  };
  $("#ej-deshacer-cierre").onclick = async () => {
    const anio = seleccion();
    if (!confirm(`¿Deshacer el cierre de ${anio}? Se eliminarán sus asientos de regularización y cierre.`)) return;
    try { await api(`/ejercicios/${anio}/cierre`, { method: "DELETE" }); toast("Cierre deshecho"); await cargar(); }
    catch (e) { fallo(e); }
  };
  $("#ej-deshacer-apertura").onclick = async () => {
    const anio = seleccion();
    if (!confirm(`¿Deshacer la apertura de ${anio}?`)) return;
    try { await api(`/ejercicios/${anio}/apertura`, { method: "DELETE" }); toast("Apertura deshecha"); await cargar(); }
    catch (e) { fallo(e); }
  };

  await cargar();
};

/* ---------- Modelo 303 oficial ---------- */

vistas.aeat303 = async () => {
  const triActual = Math.floor(new Date().getMonth() / 3) + 1;
  $("#area").innerHTML = ventana("🏛️", "Modelo 303 — Declaración trimestral de IVA", `
    <div class="toolbar">
      <label>Ejercicio<input id="m3-ejercicio" class="num" type="number" value="${ejercicio}" style="width:80px"></label>
      <label>Trimestre<select id="m3-trimestre">
        ${[1, 2, 3, 4].map((t) => `<option value="${t}" ${t === triActual ? "selected" : ""}>${t}T</option>`).join("")}
      </select></label>
      <button id="m3-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="m3-pdf">📄 Descargar PDF</button>
      <button id="m3-excel">📊 Descargar Excel</button>
    </div>
    <div id="m3-salida"></div>`);

  const parametros = () => `ejercicio=${$("#m3-ejercicio").value}&trimestre=${$("#m3-trimestre").value}`;
  const generar = async () => {
    const m = await api(`/aeat/303?${parametros()}`);
    $("#m3-salida").innerHTML = `
      <p class="aviso">${esc(m.aviso)}</p>
      <div class="grid-wrap"><table class="grid"><tbody>
        <tr class="grupo-fila"><td colspan="3">IVA DEVENGADO</td></tr>
        ${m.iva_devengado.desglose.map((f) => `<tr><td style="width:220px">Tipo ${f.tipo_iva} %</td>
          <td class="num">${eur(f.base)}</td><td class="num" style="width:140px">${eur(f.cuota)}</td></tr>`).join("") ||
          `<tr><td colspan="3" class="aviso">Sin operaciones.</td></tr>`}
        <tr class="total-fila"><td>Casilla 27 · Cuota devengada</td><td></td><td class="num">${eur(m.iva_devengado.casilla_27_cuota_devengada)}</td></tr>
        <tr class="grupo-fila"><td colspan="3">IVA DEDUCIBLE</td></tr>
        <tr><td>Casilla 28 · Base</td><td class="num">${eur(m.iva_deducible.casilla_28_base)}</td><td></td></tr>
        <tr><td>Casilla 29 · Cuota</td><td></td><td class="num">${eur(m.iva_deducible.casilla_29_cuota)}</td></tr>
        <tr class="total-fila"><td>Casilla 44 · Total a deducir</td><td></td><td class="num">${eur(m.iva_deducible.casilla_44_total_a_deducir)}</td></tr>
      </tbody></table></div>
      <div class="pie-ventana"><span>Casilla 46/69 · Resultado de la liquidación:
        <span class="dato ${m.casilla_69_resultado_liquidacion > 0 ? "neg" : "pos"}">${eur(m.casilla_69_resultado_liquidacion)}</span>
        (${m.sentido})</span></div>`;
  };
  $("#m3-generar").onclick = () => generar().catch(fallo);
  $("#m3-pdf").onclick = () => window.open(`/api/v1/aeat/303?${parametros()}&formato=pdf`, "_blank");
  $("#m3-excel").onclick = () => window.open(`/api/v1/aeat/303?${parametros()}&formato=excel`, "_blank");
  await generar();
};

/* ---------- Modelo 390 oficial ---------- */

vistas.aeat390 = async () => {
  $("#area").innerHTML = ventana("📊", "Modelo 390 — Resumen anual de IVA", `
    <div class="toolbar">
      <label>Ejercicio<input id="m9-ejercicio" class="num" type="number" value="${ejercicio}" style="width:80px"></label>
      <button id="m9-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="m9-pdf">📄 Descargar PDF</button>
      <button id="m9-excel">📊 Descargar Excel</button>
    </div>
    <div id="m9-salida"></div>`);

  const parametros = () => `ejercicio=${$("#m9-ejercicio").value}`;
  const bloque = (titulo, arr) => `
    <tr class="grupo-fila"><td colspan="3">${titulo}</td></tr>
    ${arr.map((f) => `<tr><td style="width:220px">Tipo ${f.tipo_iva} %</td><td class="num">${eur(f.base)}</td>
      <td class="num" style="width:140px">${eur(f.cuota)}</td></tr>`).join("") ||
      `<tr><td colspan="3" class="aviso">Sin operaciones.</td></tr>`}`;
  const generar = async () => {
    const m = await api(`/aeat/390?${parametros()}`);
    $("#m9-salida").innerHTML = `
      <p class="aviso">${esc(m.aviso)}</p>
      <div class="grid-wrap"><table class="grid"><tbody>
        ${bloque("IVA DEVENGADO (anual)", m.iva_devengado)}
        <tr class="total-fila"><td>Total devengado</td><td></td><td class="num">${eur(m.total_devengado)}</td></tr>
        ${bloque("IVA DEDUCIBLE (anual)", m.iva_deducible)}
        <tr class="total-fila"><td>Total deducible</td><td></td><td class="num">${eur(m.total_deducible)}</td></tr>
      </tbody></table></div>
      <div class="pie-ventana"><span>Resultado anual (informativo):
        <span class="dato">${eur(m.resultado_anual)}</span></span></div>
      <div class="grid-wrap" style="margin-top:12px"><table class="grid"><thead>
        <tr><th>Trimestre</th><th class="num">Resultado</th><th>Sentido</th></tr></thead><tbody>
        ${m.resultados_trimestrales.map((r) => `<tr><td>${r.trimestre}T</td>
          <td class="num">${eur(r.resultado)}</td><td>${esc(r.sentido)}</td></tr>`).join("")}
      </tbody></table></div>`;
  };
  $("#m9-generar").onclick = () => generar().catch(fallo);
  $("#m9-pdf").onclick = () => window.open(`/api/v1/aeat/390?${parametros()}&formato=pdf`, "_blank");
  $("#m9-excel").onclick = () => window.open(`/api/v1/aeat/390?${parametros()}&formato=excel`, "_blank");
  await generar();
};

/* ---------- Modelo 347 oficial ---------- */

vistas.aeat347 = async () => {
  $("#area").innerHTML = ventana("🧾", "Modelo 347 — Operaciones con terceros", `
    <div class="toolbar">
      <label>Ejercicio<input id="m7-ejercicio" class="num" type="number" value="${ejercicio}" style="width:80px"></label>
      <button id="m7-generar">🔍 Consultar</button>
      <span class="sep"></span>
      <button id="m7-pdf">📄 Descargar PDF</button>
      <button id="m7-excel">📊 Descargar Excel</button>
    </div>
    <div id="m7-salida"></div>`);

  const parametros = () => `ejercicio=${$("#m7-ejercicio").value}`;
  const generar = async () => {
    const m = await api(`/aeat/347?${parametros()}`);
    $("#m7-salida").innerHTML = `
      <p class="aviso">${esc(m.aviso)} Umbral: ${eur(m.umbral)}.</p>
      <div class="grid-wrap"><table class="grid"><thead>
        <tr><th>NIF</th><th>Nombre</th><th>Operación</th><th class="num">Importe anual</th>
        <th class="num">1T</th><th class="num">2T</th><th class="num">3T</th><th class="num">4T</th></tr></thead><tbody>
        ${m.registros.map((r) => `<tr><td>${esc(r.nif)}</td><td>${esc(r.nombre)}</td><td>${esc(r.operacion)}</td>
          <td class="num">${eur(r.importe_anual)}</td><td class="num">${eur(r.trimestres["1"])}</td>
          <td class="num">${eur(r.trimestres["2"])}</td><td class="num">${eur(r.trimestres["3"])}</td>
          <td class="num">${eur(r.trimestres["4"])}</td></tr>`).join("") ||
          `<tr><td colspan="8" class="aviso">Ningún tercero supera el umbral en ${$("#m7-ejercicio").value}.</td></tr>`}
      </tbody></table></div>
      <div class="pie-ventana"><span>Total declarado: <span class="dato">${eur(m.total_declarado)}</span></span></div>`;
  };
  $("#m7-generar").onclick = () => generar().catch(fallo);
  $("#m7-pdf").onclick = () => window.open(`/api/v1/aeat/347?${parametros()}&formato=pdf`, "_blank");
  $("#m7-excel").onclick = () => window.open(`/api/v1/aeat/347?${parametros()}&formato=excel`, "_blank");
  await generar();
};

/* ---------- Conciliación bancaria ---------- */

vistas.bancos = async () => {
  $("#area").innerHTML = ventana("🏦", "Conciliación bancaria (norma 43)", `
    <div class="toolbar">
      <label>Cuenta de tesorería<input list="dl-cuentas" id="bc-cuenta" value="572" style="width:90px"></label>
      <label>Fichero norma 43<input type="file" id="bc-fichero" accept=".txt,.n43,.943"></label>
      <button id="bc-importar">⬆️ Importar</button>
      <span class="sep"></span>
      <label>Estado<select id="bc-estado">
        <option value="">Todos</option><option value="false">Pendientes</option><option value="true">Conciliados</option>
      </select></label>
      <button id="bc-buscar">🔍 Actualizar</button>
    </div>
    <div class="toolbar">
      <button id="bc-conciliar" disabled>🔗 Conciliar con apunte…</button>
      <button id="bc-nuevo" disabled>➕ Conciliar creando asiento</button>
      <button id="bc-desconciliar" disabled>↩️ Desconciliar</button>
      <button id="bc-borrar" disabled>🗑 Eliminar</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-bancos"><thead>
      <tr><th>Fecha</th><th>Concepto</th><th>Documento</th><th class="num">Importe</th><th>Estado</th></tr>
    </thead><tbody></tbody></table></div>
    <div class="pie-ventana" id="bc-pie"></div>
    <p class="aviso">Formato cuaderno 43 de la AEB (registros 22/23). Los movimientos se concilian
      automáticamente si existe un apunte de igual importe y fecha en la cuenta de tesorería indicada.</p>`);

  let lista = [];
  function actualizarBotones() {
    const id = seleccion();
    const m = lista.find((x) => String(x.id) === String(id));
    $("#bc-conciliar").disabled = !m || m.conciliado;
    $("#bc-nuevo").disabled = !m || m.conciliado;
    $("#bc-desconciliar").disabled = !m || !m.conciliado;
    $("#bc-borrar").disabled = !m || m.conciliado;
  }

  const cargar = async () => {
    const p = new URLSearchParams({ cuenta: $("#bc-cuenta").value.trim() || "572" });
    if ($("#bc-estado").value) p.set("conciliado", $("#bc-estado").value);
    lista = await api("/bancos/movimientos?" + p);
    $("#grid-bancos tbody").innerHTML = lista.map((m) => `<tr data-id="${m.id}">
      <td>${fecha_es(m.fecha_operacion)}</td><td>${esc(m.concepto)}</td><td>${esc(m.documento)}</td>
      <td class="num ${m.importe >= 0 ? "" : "neg"}">${eur(m.importe)}</td>
      <td><span class="pill ${m.conciliado ? "pagada" : "pendiente"}">${m.conciliado ? "conciliado" : "pendiente"}</span></td></tr>`).join("") ||
      `<tr><td colspan="5" class="aviso">Sin movimientos importados.</td></tr>`;
    $("#bc-pie").innerHTML = `<span>Movimientos: <span class="dato">${lista.length}</span></span>
      <span>Pendientes: <span class="dato">${lista.filter((m) => !m.conciliado).length}</span></span>`;
    actualizarBotones();
  };

  const seleccion = conSeleccion("grid-bancos", ["#bc-conciliar", "#bc-nuevo", "#bc-desconciliar", "#bc-borrar"]);
  $("#grid-bancos tbody").addEventListener("click", actualizarBotones);

  $("#bc-buscar").onclick = () => cargar().catch(fallo);

  $("#bc-importar").onclick = async () => {
    const fichero = $("#bc-fichero").files[0];
    if (!fichero) { toast("Selecciona un fichero", true); return; }
    const contenido = await fichero.text();
    try {
      const nuevos = await api("/bancos/importar", {
        method: "POST",
        body: JSON.stringify({ cuenta_tesoreria: $("#bc-cuenta").value.trim() || "572", contenido }),
      });
      toast(`${nuevos.length} movimiento(s) importado(s)`);
      $("#bc-fichero").value = "";
      await cargar();
    } catch (e) { fallo(e); }
  };

  $("#bc-conciliar").onclick = () => {
    const m = lista.find((x) => String(x.id) === String(seleccion()));
    if (!m) return;
    abrirModal(`Conciliar movimiento — ${eur(m.importe)} · ${fecha_es(m.fecha_operacion)}`, `
      <form class="formulario" id="form-conciliar">
        <label class="ancho">ID del apunte contable<input id="fc-apunte" type="number" required></label>
        <p class="ancho aviso" style="padding:0">Busca el id del apunte abriendo el asiento correspondiente en Diario.
          Si el movimiento aún no está contabilizado, usa «Conciliar creando asiento».</p>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Conciliar</button>
        </div>
      </form>`);
    $("#form-conciliar").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/bancos/${m.id}/conciliar`, {
          method: "POST",
          body: JSON.stringify({ apunte_id: parseInt($("#fc-apunte").value, 10) }),
        });
        toast("Movimiento conciliado"); cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };

  $("#bc-nuevo").onclick = () => {
    const m = lista.find((x) => String(x.id) === String(seleccion()));
    if (!m) return;
    abrirModal(`Conciliar creando asiento — ${eur(m.importe)} · ${fecha_es(m.fecha_operacion)}`, `
      <form class="formulario" id="form-conciliar-nuevo">
        <label>Cuenta contrapartida<input list="dl-cuentas" id="fcn-cuenta" value="${m.importe >= 0 ? "700" : "626"}"></label>
        <label class="ancho">Concepto<input id="fcn-concepto" value="${esc(m.concepto)}" maxlength="200"></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Crear asiento y conciliar</button>
        </div>
      </form>`);
    $("#form-conciliar-nuevo").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/bancos/${m.id}/conciliar-nuevo`, {
          method: "POST",
          body: JSON.stringify({
            cuenta_contrapartida: $("#fcn-cuenta").value.trim(),
            concepto: $("#fcn-concepto").value.trim(),
          }),
        });
        toast("Asiento creado y movimiento conciliado"); cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };

  $("#bc-desconciliar").onclick = async () => {
    if (!confirm("¿Desconciliar este movimiento? El asiento contable no se modifica.")) return;
    try { await api(`/bancos/${seleccion()}/conciliacion`, { method: "DELETE" }); toast("Movimiento desconciliado"); cargar(); }
    catch (e) { fallo(e); }
  };

  $("#bc-borrar").onclick = async () => {
    if (!confirm("¿Eliminar este movimiento importado?")) return;
    try { await api(`/bancos/${seleccion()}`, { method: "DELETE" }); toast("Movimiento eliminado"); cargar(); }
    catch (e) { fallo(e); }
  };

  await cargar();
};

/* ---------- Usuarios y empresas ---------- */

vistas.usuarios = async () => {
  const empresa = miPerfil.empresas.find((e) => e.id === empresaActual);
  $("#area").innerHTML = ventana("👥", `Usuarios de ${esc(empresa.nombre)}`, `
    <div class="toolbar">
      <button id="us-invitar" ${empresa.rol === "admin" ? "" : "disabled"}>➕ Invitar usuario</button>
      <span class="sep"></span>
      <button id="us-nueva-empresa">🏢 Crear nueva empresa</button>
      <span class="sep"></span>
      <button id="us-cambiar-password">🔑 Cambiar mi contraseña</button>
      <button id="us-backup" ${empresa.rol === "admin" ? "" : "disabled"}>💾 Descargar copia de seguridad</button>
    </div>
    <div class="grid-wrap"><table class="grid" id="grid-usuarios"><thead>
      <tr><th>Email</th><th>Rol</th><th></th></tr></thead><tbody></tbody></table></div>
    <p class="aviso">Solo un administrador puede invitar o quitar usuarios. El usuario invitado debe
      tener ya una cuenta creada (pestaña "Crear cuenta" en el acceso) antes de poder añadirlo aquí.</p>`);

  const cargar = async () => {
    const lista = await api(`/empresas/${empresaActual}/usuarios`);
    $("#grid-usuarios tbody").innerHTML = lista.map((u) => `<tr>
      <td>${esc(u.email)}</td><td>${esc(u.rol)}</td>
      <td>${empresa.rol === "admin" && u.email !== miPerfil.email
        ? `<button class="secundario" onclick="quitarUsuarioGlobal(${u.usuario_id})">🗑 Quitar</button>` : ""}</td>
      </tr>`).join("");
  };

  window.quitarUsuarioGlobal = async (usuarioId) => {
    if (!confirm("¿Quitar a este usuario de la empresa?")) return;
    try {
      await api(`/empresas/${empresaActual}/usuarios/${usuarioId}`, { method: "DELETE" });
      toast("Usuario eliminado"); cargar();
    } catch (e) { fallo(e); }
  };

  $("#us-invitar").onclick = () => {
    abrirModal("Invitar usuario", `
      <form class="formulario" id="form-invitar">
        <label class="ancho">Email del usuario ya registrado<input id="iv-email" type="email" required></label>
        <label>Rol<select id="iv-rol"><option value="editor">Editor</option><option value="admin">Administrador</option></select></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Invitar</button>
        </div>
      </form>`);
    $("#form-invitar").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/empresas/${empresaActual}/usuarios`, {
          method: "POST",
          body: JSON.stringify({ email: $("#iv-email").value.trim(), rol: $("#iv-rol").value }),
        });
        toast("Usuario invitado"); cerrarModal(); cargar();
      } catch (err) { fallo(err); }
    };
  };

  $("#us-nueva-empresa").onclick = () => {
    abrirModal("Crear nueva empresa", `
      <form class="formulario" id="form-nueva-empresa">
        <label class="ancho">Nombre de la empresa<input id="ne-nombre" required maxlength="150"></label>
        <label class="ancho">NIF<input id="ne-nif" maxlength="20"></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Crear</button>
        </div>
      </form>`);
    $("#form-nueva-empresa").onsubmit = async (e) => {
      e.preventDefault();
      try {
        const nueva = await api("/empresas", {
          method: "POST",
          body: JSON.stringify({ nombre: $("#ne-nombre").value.trim(), nif: $("#ne-nif").value.trim() }),
        });
        miPerfil.empresas.push({ id: nueva.id, nombre: nueva.nombre, rol: "admin" });
        empresaActual = nueva.id;
        toast("Empresa creada"); cerrarModal();
        pintarEmpresa();
        await recargarCuentas();
        await abrirVista("inicio");
      } catch (err) { fallo(err); }
    };
  };

  $("#us-cambiar-password").onclick = () => {
    abrirModal("Cambiar mi contraseña", `
      <form class="formulario" id="form-cambiar-password">
        <label class="ancho">Contraseña actual<input id="cp-actual" type="password" required autocomplete="current-password"></label>
        <label class="ancho">Contraseña nueva (mín. 8 caracteres)<input id="cp-nueva" type="password" required minlength="8" autocomplete="new-password"></label>
        <div class="botones-form ancho">
          <button type="button" class="secundario" onclick="document.getElementById('modal').classList.add('oculto')">Cancelar</button>
          <button type="submit" class="principal">Cambiar contraseña</button>
        </div>
      </form>`);
    $("#form-cambiar-password").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/auth/password", {
          method: "PUT",
          body: JSON.stringify({
            password_actual: $("#cp-actual").value, password_nueva: $("#cp-nueva").value,
          }),
        });
        toast("Contraseña actualizada"); cerrarModal();
      } catch (err) { fallo(err); }
    };
  };

  $("#us-backup").onclick = () => {
    window.open(`/api/v1/empresas/${empresaActual}/exportar`, "_blank");
  };

  await cargar();
};

/* ---------- Asistente de IA ---------- */

vistas.asistente = async () => {
  const empresaNombre = miPerfil.empresas.find((e) => e.id === empresaActual)?.nombre || "";
  $("#area").innerHTML = ventana("🤖", "Asistente de IA (local, vía Ollama)", `
    <div id="ia-estado" class="aviso"></div>
    <div id="ia-chat" style="display:flex;flex-direction:column;gap:10px;padding:10px;max-height:calc(100vh - 420px);overflow:auto"></div>
    <div class="toolbar">
      <input id="ia-pregunta" placeholder="Pregunta sobre tus datos contables…" style="flex:1;min-width:260px">
      <button id="ia-enviar">➤ Enviar</button>
      <button id="ia-limpiar" class="secundario">🧹 Nueva conversación</button>
    </div>
    <p class="aviso">El modelo solo puede consultar datos de <b>${esc(empresaNombre)}</b> a través de
      herramientas de solo lectura; nunca modifica nada ni ve otras empresas.</p>`);

  let historial = [];

  const comprobarEstado = async () => {
    const estado = await api("/ia/estado");
    const div = $("#ia-estado");
    if (!estado.disponible) {
      div.innerHTML = `⚠️ Ollama no está disponible en <code>${esc(estado.url)}</code>. Instálalo desde
        <a href="https://ollama.com" target="_blank" rel="noopener">ollama.com</a>, asegúrate de que está en
        marcha (<code>ollama serve</code>, normalmente automático) y descarga el modelo:
        <code>ollama pull ${esc(estado.modelo)}</code>.`;
      $("#ia-enviar").disabled = true;
    } else if (!estado.modelo_descargado) {
      div.innerHTML = `⚠️ Ollama está en marcha pero el modelo <code>${esc(estado.modelo)}</code> no está
        descargado. Ejecuta <code>ollama pull ${esc(estado.modelo)}</code>.
        ${estado.modelos_descargados.length ? "Descargados: " + estado.modelos_descargados.map(esc).join(", ") : ""}`;
      $("#ia-enviar").disabled = true;
    } else {
      div.innerHTML = `✓ Conectado a Ollama (<code>${esc(estado.modelo)}</code>).`;
      $("#ia-enviar").disabled = false;
    }
  };

  const agregarMensaje = (rol, texto) => {
    const burbuja = document.createElement("div");
    burbuja.style.cssText = rol === "user"
      ? "align-self:flex-end;background:var(--naranja-suave);border-radius:8px;padding:8px 12px;max-width:75%;white-space:pre-wrap"
      : "align-self:flex-start;background:var(--chrome);border:1px solid var(--borde);border-radius:8px;padding:8px 12px;max-width:75%;white-space:pre-wrap";
    burbuja.textContent = texto;
    $("#ia-chat").appendChild(burbuja);
    $("#ia-chat").scrollTop = $("#ia-chat").scrollHeight;
  };

  const enviar = async () => {
    const pregunta = $("#ia-pregunta").value.trim();
    if (!pregunta) return;
    agregarMensaje("user", pregunta);
    $("#ia-pregunta").value = "";
    $("#ia-enviar").disabled = true;
    const pensando = document.createElement("div");
    pensando.className = "aviso";
    pensando.style.padding = "0";
    pensando.textContent = "Pensando… (puede tardar si el modelo corre en CPU)";
    $("#ia-chat").appendChild(pensando);
    $("#ia-chat").scrollTop = $("#ia-chat").scrollHeight;
    try {
      const r = await api("/ia/preguntar", { method: "POST", body: JSON.stringify({ pregunta, historial }) });
      pensando.remove();
      agregarMensaje("assistant", r.respuesta);
      historial.push({ role: "user", content: pregunta }, { role: "assistant", content: r.respuesta });
      if (r.herramientas_usadas.length) {
        const detalle = document.createElement("div");
        detalle.className = "aviso";
        detalle.style.cssText = "padding:0;align-self:flex-start";
        detalle.textContent = "🔎 Consultado: " + r.herramientas_usadas.map((h) => h.herramienta).join(", ");
        $("#ia-chat").appendChild(detalle);
      }
    } catch (e) {
      pensando.remove();
      fallo(e);
    } finally {
      $("#ia-enviar").disabled = false;
      $("#ia-pregunta").focus();
    }
  };

  $("#ia-enviar").onclick = enviar;
  $("#ia-pregunta").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); enviar(); } };
  $("#ia-limpiar").onclick = () => { historial = []; $("#ia-chat").innerHTML = ""; };

  await comprobarEstado();
  $("#ia-pregunta").focus();
};

/* ---------- arranque y autenticación ---------- */

function pintarEjercicio() {
  $("#titlebar-ejercicio").textContent = ejercicio;
  $("#status-ejercicio").textContent = `Ejercicio ${ejercicio}`;
}

function pintarEmpresa() {
  const empresa = miPerfil.empresas.find((e) => e.id === empresaActual);
  if (!empresa) return;
  $("#titlebar-empresa").textContent = empresa.nombre;
  $("#status-empresa").textContent = empresa.nombre;
  $("#sel-empresa").innerHTML = miPerfil.empresas
    .map((e) => `<option value="${e.id}" ${e.id === empresaActual ? "selected" : ""}>${esc(e.nombre)}</option>`)
    .join("");
}

function mostrarLogin() {
  $("#pantalla-login").classList.remove("oculto");
  $("#app").classList.add("oculto");
  mostrarFormularioLogin("login");
}

async function mostrarApp() {
  $("#pantalla-login").classList.add("oculto");
  $("#app").classList.remove("oculto");
  pintarEmpresa();
  const actual = new Date().getFullYear();
  $("#sel-ejercicio").innerHTML = Array.from({ length: 8 }, (_, i) => actual + 1 - i)
    .map((a) => `<option value="${a}" ${a === ejercicio ? "selected" : ""}>${a}</option>`).join("");
  pintarEjercicio();
  pintarRibbon("inicio");
  await recargarCuentas();
  await abrirVista("inicio");
}

async function iniciarSesionComprobando() {
  try {
    miPerfil = await api("/auth/me");
    if (!miPerfil.empresas.length) {
      toast("Tu usuario no pertenece a ninguna empresa todavía", true);
      mostrarLogin();
      return;
    }
    empresaActual = miPerfil.empresas[0].id;
    await mostrarApp();
  } catch (e) {
    mostrarLogin();
  }
}

const FORMULARIOS_LOGIN = ["login", "registro", "olvide", "restablecer"];

function mostrarFormularioLogin(nombre) {
  FORMULARIOS_LOGIN.forEach((f) => $(`#form-${f}`).classList.toggle("oculto", f !== nombre));
  $$("#login-pestanas button").forEach((b) => b.classList.toggle("activo", b.dataset.form === nombre));
}

$$("#login-pestanas button").forEach((b) => {
  b.onclick = () => mostrarFormularioLogin(b.dataset.form);
});

$("#form-login").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: $("#li-email").value.trim(), password: $("#li-password").value }),
    });
    await iniciarSesionComprobando();
  } catch (err) { fallo(err); }
};

$("#form-registro").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/auth/registro", {
      method: "POST",
      body: JSON.stringify({
        email: $("#re-email").value.trim(),
        password: $("#re-password").value,
        nombre: $("#re-nombre").value.trim(),
        empresa_nombre: $("#re-empresa").value.trim(),
      }),
    });
    await iniciarSesionComprobando();
  } catch (err) { fallo(err); }
};

$("#link-olvide").onclick = (e) => {
  e.preventDefault();
  mostrarFormularioLogin("olvide");
};

$("#form-olvide").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const r = await api("/auth/olvide-password", {
      method: "POST",
      body: JSON.stringify({ email: $("#ol-email").value.trim() }),
    });
    toast(r.mensaje);
    mostrarFormularioLogin("restablecer");
  } catch (err) { fallo(err); }
};

$("#form-restablecer").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/auth/restablecer-password", {
      method: "POST",
      body: JSON.stringify({ token: $("#rs-token").value.trim(), password_nueva: $("#rs-password").value }),
    });
    toast("Contraseña restablecida, ya puedes entrar");
    mostrarFormularioLogin("login");
  } catch (err) { fallo(err); }
};

$("#link-salir").onclick = async (e) => {
  e.preventDefault();
  try { await api("/auth/logout", { method: "POST" }); } catch { /* ignorar */ }
  miPerfil = null;
  empresaActual = null;
  mostrarLogin();
};

$("#sel-empresa").onchange = async (e) => {
  empresaActual = parseInt(e.target.value, 10);
  pintarEmpresa();
  try {
    await recargarCuentas();
    await abrirVista("inicio");
  } catch (err) { fallo(err); }
};

$("#sel-ejercicio").onchange = (e) => {
  ejercicio = parseInt(e.target.value, 10);
  pintarEjercicio();
  vistas[vistaActual]().catch(fallo);
};

iniciarSesionComprobando();
