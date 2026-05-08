// Punch — client JS
// Handles: live timer display, billing mode toggle, line item management,
// timezone conversion for datetime-local inputs

// ── Timezone helpers ────────────────────────────────────────────────────────

// Convert a UTC ISO string (e.g. "2026-05-07T11:42:00Z") to a value
// suitable for <input type="datetime-local"> (local time, no TZ).
function utcISOToLocalInput(utcISO) {
  if (!utcISO) return "";
  const d = new Date(utcISO);
  if (isNaN(d.getTime())) return "";
  // Build "YYYY-MM-DDTHH:MM" in LOCAL time
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Convert a datetime-local input value (local time) to a UTC string
// the server can parse as naive UTC: "YYYY-MM-DDTHH:MM"
function localInputToUTCString(localVal) {
  if (!localVal) return "";
  const d = new Date(localVal); // interpreted as local
  if (isNaN(d.getTime())) return "";
  const pad = n => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

// Initialize a time entry form (new or edit).
// - On load: any input with [data-utc-source] gets its value set from a
//   UTC ISO string in that data attribute, converted to local.
// - On submit: any [data-utc-target] input gets the UTC version of its
//   sibling input's value.
function initTimeEntryForm() {
  // Populate inputs from UTC sources on load
  document.querySelectorAll("input[data-utc-source]").forEach(input => {
    const utcISO = input.dataset.utcSource;
    if (utcISO) {
      input.value = utcISOToLocalInput(utcISO);
    }
  });

  // On submit, write UTC values into hidden _utc fields
  document.querySelectorAll("form[data-time-form]").forEach(form => {
    form.addEventListener("submit", () => {
      form.querySelectorAll("input[data-utc-target]").forEach(hidden => {
        const sourceName = hidden.dataset.utcTarget;
        const visible = form.querySelector(`input[name="${sourceName}"]`);
        if (visible) {
          hidden.value = localInputToUTCString(visible.value);
        }
      });
    });
  });
}

// ── Live timer ──────────────────────────────────────────────────────────────

let timerInterval = null;

function formatElapsed(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [
    h.toString().padStart(2, "0"),
    m.toString().padStart(2, "0"),
    s.toString().padStart(2, "0"),
  ].join(":");
}

function startLiveTimer(startedAtISO) {
  const clock = document.getElementById("punch-clock");
  if (!clock) return;

  const started = new Date(startedAtISO);

  function tick() {
    const elapsed = Math.floor((Date.now() - started.getTime()) / 1000);
    clock.textContent = formatElapsed(Math.max(0, elapsed));
  }

  tick();
  timerInterval = setInterval(tick, 1000);
}

// ── Punch screen initialization ─────────────────────────────────────────────

async function initPunchScreen() {
  if (window.PUNCH_RUNNING) return;
  const clock = document.getElementById("punch-clock");
  if (!clock) return;

  try {
    const resp = await fetch("/time/status");
    const data = await resp.json();

    if (data.running) {
      clock.classList.remove("idle");
      document.getElementById("punch-running-client")?.textContent && (
        document.getElementById("punch-running-client").textContent = data.client_name
      );
      startLiveTimer(data.started_at);
    } else {
      clock.textContent = "00:00:00";
      clock.classList.add("idle");
    }
  } catch (e) {
    clock.textContent = "--:--:--";
  }
}

// ── Billing mode toggle (client form) ───────────────────────────────────────

function initBillingModeToggle() {
  const radios = document.querySelectorAll('input[name="billing_mode"]');
  if (!radios.length) return;

  function update(val) {
    document.querySelectorAll(".billing-mode-section").forEach(el => {
      el.classList.toggle("active", el.dataset.mode === val);
    });
  }

  radios.forEach(r => r.addEventListener("change", () => update(r.value)));

  const checked = document.querySelector('input[name="billing_mode"]:checked');
  if (checked) update(checked.value);
}

// ── Line item management (manual invoice) ───────────────────────────────────

function initLineItems() {
  const container = document.getElementById("line-items-container");
  const addBtn = document.getElementById("add-line-item");
  if (!container || !addBtn) return;

  function calcRowTotal(row) {
    const qty = parseFloat(row.querySelector(".item-qty")?.value) || 0;
    const price = parseFloat(row.querySelector(".item-price")?.value) || 0;
    const totalEl = row.querySelector(".item-total");
    if (totalEl) totalEl.textContent = "$" + (qty * price).toFixed(2);
    calcInvoiceTotal();
  }

  function calcInvoiceTotal() {
    let total = 0;
    document.querySelectorAll(".line-item-row").forEach(row => {
      const qty = parseFloat(row.querySelector(".item-qty")?.value) || 0;
      const price = parseFloat(row.querySelector(".item-price")?.value) || 0;
      total += qty * price;
    });
    const totalEl = document.getElementById("invoice-total-display");
    if (totalEl) totalEl.textContent = "$" + total.toFixed(2);
  }

  function bindRow(row) {
    row.querySelector(".item-qty")?.addEventListener("input", () => calcRowTotal(row));
    row.querySelector(".item-price")?.addEventListener("input", () => calcRowTotal(row));
    row.querySelector(".remove-line-item")?.addEventListener("click", () => {
      if (container.querySelectorAll(".line-item-row").length > 1) {
        row.remove();
        calcInvoiceTotal();
      }
    });
  }

  container.querySelectorAll(".line-item-row").forEach(bindRow);

  addBtn.addEventListener("click", () => {
    const template = container.querySelector(".line-item-row");
    const clone = template.cloneNode(true);
    clone.querySelectorAll("input").forEach(i => i.value = "");
    clone.querySelector(".item-total").textContent = "$0.00";
    container.appendChild(clone);
    bindRow(clone);
  });
}

// ── Confirm dangerous actions ────────────────────────────────────────────────

function initConfirmForms() {
  document.querySelectorAll("[data-confirm]").forEach(el => {
    el.addEventListener("submit", e => {
      if (!confirm(el.dataset.confirm)) e.preventDefault();
    });
    el.addEventListener("click", e => {
      if (el.tagName === "BUTTON" && el.dataset.confirm) {
        if (!confirm(el.dataset.confirm)) e.preventDefault();
      }
    });
  });
}

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initPunchScreen();
  initBillingModeToggle();
  initLineItems();
  initConfirmForms();
  initTimeEntryForm();
});