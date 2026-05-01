// Punch — client JS
// Handles: live timer display, billing mode toggle, line item management

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

  // Set initial state
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

  // Bind existing rows
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
    // Also handle buttons that are inside forms
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
});
