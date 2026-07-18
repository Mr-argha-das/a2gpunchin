const authHeaders = () => {
  return {"Content-Type": "application/json"};
};

function toast(message, tone = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return alert(message);
  const item = document.createElement("div");
  item.className = `toast align-items-center text-bg-${tone} border-0`;
  item.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  container.appendChild(item);
  new bootstrap.Toast(item).show();
}

async function apiFetch(url, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = {...(isFormData ? {} : authHeaders()), ...(options.headers || {})};
  const response = await fetch(url, {...options, credentials: "same-origin", headers});
  if (!response.ok) {
    let detail = "Request failed";
    const text = await response.text();
    if (text) {
      try {
        const payload = JSON.parse(text);
        detail = payload.detail || text;
      } catch (_) {
        detail = text;
      }
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function formBody(form) {
  const body = Object.fromEntries(new FormData(form).entries());
  form.querySelectorAll("input[type='checkbox']").forEach((input) => {
    if (!input.name) return;
    const group = form.querySelectorAll(`input[type='checkbox'][name='${CSS.escape(input.name)}']`);
    if (group.length > 1) {
      body[input.name] = Array.from(group).filter((item) => item.checked).map((item) => item.value);
    } else {
      body[input.name] = input.checked;
    }
  });
  Object.keys(body).forEach((key) => {
    if (body[key] === "") delete body[key];
    if (key === "face_embedding" && typeof body[key] === "string") {
      body[key] = JSON.parse(body[key]);
    }
  });
  if (body.portal_access !== true && body.portal_access !== "true") {
    delete body.login_password;
    delete body.access_level;
    delete body.module_access;
  }
  return body;
}

function currentLocationPayload(callback) {
  navigator.geolocation.getCurrentPosition((position) => {
    callback({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      device_info: navigator.userAgent,
      browser_fingerprint: `${screen.width}x${screen.height}-${navigator.language}`,
    });
  }, () => toast("Location permission is required", "danger"));
}

function tableCell(value) {
  const text = document.createTextNode(value ?? "");
  const cell = document.createElement("td");
  cell.appendChild(text);
  return cell;
}

function actionCell(item, table) {
  const cell = document.createElement("td");
  const editModal = table.dataset.editModal;
  if (!editModal || !item.id) {
    cell.textContent = "-";
    return cell;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-sm btn-outline-primary table-edit-button";
  button.dataset.api = `${table.dataset.api}/${item.id}`;
  button.dataset.modal = editModal;
  button.dataset.title = table.dataset.editTitle || "Edit";
  button.textContent = "Edit";
  cell.appendChild(button);
  return cell;
}

function tableUrl(table) {
  const params = new URLSearchParams(table.dataset.query || "");
  params.set("page", table.dataset.page || "1");
  params.set("page_size", table.dataset.pageSize || table.dataset.pageSizeDefault || "25");
  const query = params.toString();
  return `${table.dataset.api}${query ? `?${query}` : ""}`;
}

function ensurePager(table) {
  if (table.nextElementSibling?.classList.contains("table-pager")) {
    return table.nextElementSibling;
  }
  const wrapper = document.createElement("div");
  wrapper.className = "table-pager";
  wrapper.innerHTML = `
    <div class="table-pager__left">
      <label class="form-label mb-0">Rows</label>
      <select class="form-select form-select-sm table-page-size"></select>
      <span class="table-page-summary"></span>
    </div>
    <div class="table-pager__right">
      <button class="btn btn-sm btn-outline-secondary table-prev" type="button">Prev</button>
      <span class="table-page-count"></span>
      <button class="btn btn-sm btn-outline-secondary table-next" type="button">Next</button>
    </div>`;
  table.insertAdjacentElement("afterend", wrapper);
  const select = wrapper.querySelector(".table-page-size");
  const sizes = (table.dataset.pageSizes || "25,50,75,100").split(",").map((size) => size.trim()).filter(Boolean);
  sizes.forEach((size) => {
    const option = document.createElement("option");
    option.value = size;
    option.textContent = size;
    select.appendChild(option);
  });
  table.dataset.pageSizeDefault = table.dataset.pageSize || sizes[0] || "25";
  table.dataset.pageSize = table.dataset.pageSizeDefault;
  select.value = table.dataset.pageSize;
  select.addEventListener("change", () => {
    table.dataset.pageSize = select.value;
    table.dataset.page = "1";
    hydrateDataTable(table);
  });
  wrapper.querySelector(".table-prev").addEventListener("click", () => {
    table.dataset.page = String(Math.max(1, Number(table.dataset.page || "1") - 1));
    hydrateDataTable(table);
  });
  wrapper.querySelector(".table-next").addEventListener("click", () => {
    const maxPage = Number(table.dataset.maxPage || "1");
    table.dataset.page = String(Math.min(maxPage, Number(table.dataset.page || "1") + 1));
    hydrateDataTable(table);
  });
  return wrapper;
}

function renderPager(table, result) {
  const pager = table.nextElementSibling?.classList.contains("table-pager") ? table.nextElementSibling : ensurePager(table);
  const page = Number(result.page || table.dataset.page || 1);
  const pageSize = Number(result.page_size || table.dataset.pageSize || 25);
  const total = Number(result.total || 0);
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  table.dataset.page = String(page);
  table.dataset.pageSize = String(pageSize);
  table.dataset.maxPage = String(maxPage);
  const start = total ? (page - 1) * pageSize + 1 : 0;
  const end = Math.min(total, page * pageSize);
  pager.querySelector(".table-page-summary").textContent = `Showing ${start}-${end} of ${total}`;
  pager.querySelector(".table-page-count").textContent = `Page ${page} of ${maxPage}`;
  pager.querySelector(".table-prev").disabled = page <= 1;
  pager.querySelector(".table-next").disabled = page >= maxPage;
  pager.querySelector(".table-page-size").value = String(pageSize);
}

function employeeInitials(item) {
  const first = String(item.first_name || "").trim()[0] || "";
  const last = String(item.last_name || "").trim()[0] || "";
  return `${first}${last}`.toUpperCase() || String(item.employee_code || "E").trim()[0] || "E";
}

function employeeCardStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("terminated") || normalized.includes("inactive")) return "employee-card__status--danger";
  if (normalized.includes("active")) return "employee-card__status--active";
  return "employee-card__status--muted";
}

function displayNameWithoutCode(value) {
  return String(value || "-").replace(/\s*\([^)]*\)\s*$/, "") || "-";
}

function compactValue(value) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "-";
  if (value === true) return "Yes";
  if (value === false) return "No";
  return value === undefined || value === null || value === "" ? "-" : value;
}

function formatShortDate(value) {
  if (!value || value === "-") return "-";
  const text = String(value);
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) return `${match[3]}-${match[2]}-${match[1].slice(2)}`;
  const parsed = new Date(text);
  if (!Number.isNaN(parsed.getTime())) {
    const day = String(parsed.getDate()).padStart(2, "0");
    const month = String(parsed.getMonth() + 1).padStart(2, "0");
    const year = String(parsed.getFullYear()).slice(2);
    return `${day}-${month}-${year}`;
  }
  const named = text.match(/^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$/);
  if (named) {
    const months = {jan: "01", feb: "02", mar: "03", apr: "04", may: "05", jun: "06", jul: "07", aug: "08", sep: "09", oct: "10", nov: "11", dec: "12"};
    return `${named[1].padStart(2, "0")}-${months[named[2].toLowerCase()] || named[2]}-${named[3].slice(2)}`;
  }
  return text;
}

function formatDateTime(value) {
  if (!value || value === "-") return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  const day = String(parsed.getDate()).padStart(2, "0");
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const year = String(parsed.getFullYear()).slice(2);
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${day}-${month}-${year} ${hours}:${minutes}`;
}

function employeeViewField(label, value) {
  return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(compactValue(value))}</strong></div>`;
}

function employeeViewSection(title, fields) {
  return `
    <section class="employee-view__section">
      <h4 class="employee-view__section-title">${escapeHtml(title)}</h4>
      <div class="employee-view__grid">
        ${fields.map(([label, value]) => employeeViewField(label, value)).join("")}
      </div>
    </section>`;
}

function employeeAssetList(assets) {
  if (!assets.length) {
    return `<div class="employee-view__empty">No assets assigned</div>`;
  }
  return `
    <div class="employee-view__assets">
      ${assets.map((asset) => `
        <div class="employee-view__asset">
          <strong>${escapeHtml(asset.asset_name || asset.asset_id || "Asset")}</strong>
          <span>${escapeHtml(asset.asset_type || "-")} · ${escapeHtml(asset.status || "-")}</span>
          <span>${escapeHtml(asset.brand_model || "-")} · ${escapeHtml(asset.serial_number || "-")}</span>
        </div>
      `).join("")}
    </div>`;
}

function employeeDocumentList(documents) {
  if (!documents.length) {
    return `<div class="employee-view__empty">No documents uploaded</div>`;
  }
  return `
    <div class="employee-document-list__items">
      ${documents.map((document) => `
        <div class="employee-document-item">
          <div>
            <strong>${escapeHtml(document.document_name || "Document")}</strong>
            <span>${escapeHtml(document.original_filename || "-")}</span>
            <span>Uploaded ${escapeHtml(formatDateTime(document.uploaded_at))}</span>
          </div>
          <a class="btn btn-sm btn-outline-primary" href="${escapeHtml(document.download_url)}">Download</a>
        </div>
      `).join("")}
    </div>`;
}

async function loadEmployeeDocuments(employeeId) {
  const result = await apiFetch(`/api/employees/${employeeId}/documents`);
  return result.items || [];
}

async function openEmployeeDocuments(item) {
  const modal = document.getElementById("employeeDocumentsModal");
  const form = document.getElementById("employeeDocumentForm");
  const list = document.getElementById("employeeDocumentList");
  if (!modal || !form || !list) return;
  form.dataset.employeeId = item.id;
  form.reset();
  list.innerHTML = `<div class="employee-card-empty">Loading documents...</div>`;
  new bootstrap.Modal(modal).show();
  try {
    list.innerHTML = employeeDocumentList(await loadEmployeeDocuments(item.id));
  } catch (error) {
    list.innerHTML = `<div class="employee-card-empty">${escapeHtml(error.message || "Unable to load documents")}</div>`;
  }
}

function renderEmployeeView(summary, detail, assets, documents = []) {
  const item = {...summary, ...detail};
  const fullName = [item.first_name, item.last_name].filter(Boolean).join(" ") || "Employee";
  const department = displayNameWithoutCode(summary.department || item.department_id);
  const branch = displayNameWithoutCode(summary.branch || item.branch_id);
  const shift = summary.shift || item.shift_id;
  const bankingFields = [
    ["Account Holder", item.account_holder_name || item.bank_account_name],
    ["Bank Name", item.bank_name],
    ["Account Number", item.account_number || item.bank_account_number],
    ["IFSC Code", item.ifsc_code || item.bank_ifsc],
    ["UAN", item.uan],
    ["PF Number", item.pf_number],
    ["ESI Number", item.esi_number],
  ].filter(([, value]) => compactValue(value) !== "-");
  return `
    <div class="employee-view">
      <div class="employee-view__head">
        <div class="employee-card__avatar">${escapeHtml(employeeInitials(item))}</div>
        <div>
          <h3>${escapeHtml(fullName)}</h3>
          <p>${escapeHtml(item.employee_code || "-")} · ${escapeHtml(item.designation || "No designation")}</p>
        </div>
        <span class="employee-card__status ${employeeCardStatusClass(item.status)}">${escapeHtml(item.status || "-")}</span>
      </div>
      ${employeeViewSection("Personal Details", [
        ["First Name", item.first_name],
        ["Last Name", item.last_name],
        ["Father Name", item.father_name],
        ["Mother Name", item.mother_name],
        ["Date of Birth", formatShortDate(item.date_of_birth)],
        ["Gender", item.gender],
        ["Marital Status", item.marital_status],
        ["Phone", item.phone],
        ["Emergency Contact", item.emergency_contact_number],
        ["Email", item.email],
        ["Current Address", item.current_address],
        ["Permanent Address", item.permanent_address],
      ])}
      ${employeeViewSection("Official Details", [
        ["Staff ID", item.employee_code],
        ["Role", item.staff_role],
        ["Designation", item.designation],
        ["Department", department],
        ["Branch", branch],
        ["Shift", shift],
        ["Joining Date", formatShortDate(item.joining_date)],
        ["Status", item.status],
        ["Office Email", item.office_email],
        ["Face Enrollment", summary.face || (item.face_enrolled ? "Enrolled" : "Not Enrolled")],
        ["Portal Access", item.portal_access],
        ["Access Level", item.access_level],
        ["Modules", item.module_access],
      ])}
      ${employeeViewSection("Banking Details", bankingFields.length ? bankingFields : [["Banking Details", "No banking details available"]])}
      ${employeeViewSection("Documents & Other Details", [
        ["Aadhar Number", item.aadhar_number],
        ["PAN Number", item.pan_number],
        ["Qualification", item.qualification],
        ["Work Experience", item.work_experience],
        ["Note", item.note],
        ["Profile Photo", item.profile_photo],
      ])}
      <section class="employee-view__section">
      <h4 class="employee-view__section-title">Document Rack</h4>
      ${employeeDocumentList(documents)}
      </section>
      <section class="employee-view__section">
      <h4 class="employee-view__section-title">Allocated Assets</h4>
      ${employeeAssetList(assets)}
      </section>
    </div>`;
}

function renderEmployeeCards(container, result) {
  renderPager(container, result);
  const items = result.items || [];
  const countLabel = document.getElementById("employeeCountLabel");
  if (countLabel) {
    const total = Number(result.total || 0);
    countLabel.innerHTML = total ? `<span class="count-accent">${total}</span> Employee` : "Employee";
  }
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = `<div class="employee-card-empty">No employees found</div>`;
    return;
  }
  const editModal = container.dataset.editModal;
  const editTitle = container.dataset.editTitle || "Edit Employee";
  container.innerHTML = items.map((item) => {
    const fullName = [item.first_name, item.last_name].filter(Boolean).join(" ") || "Employee";
    const encoded = encodeURIComponent(JSON.stringify(item));
    const api = `${container.dataset.api}/${item.id}`;
    const statusClass = employeeCardStatusClass(item.status);
    return `
      <article class="employee-card" data-employee="${encoded}">
        
        <div class="employee-card__portrait">
          <div class="employee-card__avatar">
            ${escapeHtml(employeeInitials(item))}
            <span class="employee-card__presence ${statusClass}"></span>
          </div>
          <div class="employee-card__identity">
            <strong>${escapeHtml(fullName)}</strong>
            <span>${escapeHtml(item.designation || item.staff_role || "Employee")}</span>
            <span class="employee-card__code">${escapeHtml(item.employee_code || "-")}</span>
          </div>
        </div>
      
        <div class="employee-card__meta employee-card__meta--split">
          <div><span>Department</span><strong>${escapeHtml(displayNameWithoutCode(item.department))}</strong></div>
          <div><span>Hired Date</span><strong>${escapeHtml(formatShortDate(item.joining_date))}</strong></div>
        </div>
        <div class="employee-card__contact">
          <span>✉ ${escapeHtml(item.email || "-")}</span>
          <span>☎ ${escapeHtml(item.phone || "-")}</span>
        </div>
        <div class="employee-card__footer">
          <div>
            <button class="btn btn-sm btn-outline-secondary employee-view-button" type="button">View</button>
            <button class="btn btn-sm btn-outline-secondary employee-documents-button" type="button">Docs</button>
            <button class="btn btn-sm btn-outline-primary table-edit-button" type="button" data-api="${escapeHtml(api)}" data-modal="${escapeHtml(editModal || "")}" data-title="${escapeHtml(editTitle)}">Edit</button>
          </div>
        </div>
      </article>`;
  }).join("");
}

async function hydrateDataTable(table) {
  if (!table.dataset.page) table.dataset.page = "1";
  ensurePager(table);
  if (table.dataset.view === "employee-cards") {
    table.innerHTML = `<div class="employee-card-empty">Loading employees...</div>`;
    try {
      const result = await apiFetch(tableUrl(table));
      renderEmployeeCards(table, result);
    } catch (error) {
      table.innerHTML = `<div class="employee-card-empty">${escapeHtml(error.message || "Unable to load employees")}</div>`;
    }
    return;
  }
  const columns = (table.dataset.columns || "").split(",").map((column) => column.trim()).filter(Boolean);
  const columnCount = table.querySelectorAll("thead th").length || columns.length || 1;
  const body = table.querySelector("tbody") || table.createTBody();
  body.innerHTML = "";
  try {
    const result = await apiFetch(tableUrl(table));
    renderPager(table, result);
    const items = result.items || [];
    const rows = columns.length
      ? items.map((item) => columns.map((column) => ({column, item, value: item[column] ?? ""})))
      : items.map((item) => Object.values(item).map((value) => ({column: "", item, value})));
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = tableCell("No records found");
      cell.colSpan = columnCount;
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }
    rows.forEach((values) => {
      const row = document.createElement("tr");
      values.forEach(({column, item, value}) => {
        row.appendChild(column === "actions" ? actionCell(item, table) : tableCell(value));
      });
      body.appendChild(row);
    });
  } catch (error) {
    const row = document.createElement("tr");
    const cell = tableCell(error.message || "Unable to load records");
    cell.colSpan = columnCount;
    row.appendChild(cell);
    body.appendChild(row);
  }
}

function optionLabel(item, kind) {
  if (kind === "branch") {
    return `${item.branch_name || "Branch"} (${item.branch_code || item.id})`;
  }
  if (kind === "employee") {
    return `${item.employee_code || "Employee"} - ${[item.first_name, item.last_name].filter(Boolean).join(" ") || item.email || item.id}`;
  }
  if (kind === "department") {
    return `${item.department_name || "Department"} (${item.department_code || item.id})`;
  }
  if (kind === "shift") {
    return `${item.shift_name || "Shift"} (${item.start_time || "--"}-${item.end_time || "--"})`;
  }
  if (kind === "company") {
    return `${item.company_name || "Company"} (${item.company_code || item.id})`;
  }
  return item.name || item.title || item.id;
}

async function loadSelectOptions() {
  const selects = document.querySelectorAll("select.option-loader");
  await Promise.all(Array.from(selects).map(async (select) => {
    try {
      const items = await loadOptionItems(select.dataset.source, select.dataset.loadAll === "true");
      const placeholder = select.querySelector("option[value='']")?.textContent || "Select";
      select.innerHTML = `<option value="">${placeholder}</option>`;
      items.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = optionLabel(item, select.dataset.kind);
        if (select.dataset.kind === "company") {
          option.dataset.tenantId = item.tenant_id || "";
        }
        select.appendChild(option);
      });
      if (select.dataset.defaultValue !== undefined) {
        select.value = select.dataset.defaultValue;
      }
    } catch (error) {
      if (select.dataset.kind === "company") {
        const placeholder = select.querySelector("option[value='']")?.textContent || "Use current company";
        select.innerHTML = `<option value="">${placeholder}</option>`;
        return;
      }
      select.innerHTML = `<option value="">Unable to load options</option>`;
    }
  }));
}

async function loadDatalistOptions() {
  const inputs = document.querySelectorAll("input.option-datalist");
  await Promise.all(Array.from(inputs).map(async (input) => {
    try {
      const list = document.getElementById(input.getAttribute("list"));
      if (!list) return;
      const items = await loadOptionItems(input.dataset.source, input.dataset.loadAll === "true");
      const labelToId = {};
      list.innerHTML = "";
      items.forEach((item) => {
        const label = optionLabel(item, input.dataset.kind);
        labelToId[label] = item.id;
        const option = document.createElement("option");
        option.value = label;
        list.appendChild(option);
      });
      input.dataset.labelToId = JSON.stringify(labelToId);
    } catch (error) {
      input.placeholder = "Unable to load candidates";
    }
  }));
}

const optionItemsCache = new Map();

async function loadOptionItems(source, loadAll = false) {
  const cacheKey = `${source}|${loadAll ? "all" : "page"}`;
  if (optionItemsCache.has(cacheKey)) {
    return optionItemsCache.get(cacheKey);
  }
  const request = (async () => {
    if (!loadAll) {
      const result = await apiFetch(source);
      return result.items || [];
    }
    const items = [];
    let page = 1;
    let total = 0;
    do {
      const separator = source.includes("?") ? "&" : "?";
      const result = await apiFetch(`${source}${separator}page=${page}&page_size=100`);
      items.push(...(result.items || []));
      total = Number(result.total || items.length);
      page += 1;
    } while (items.length < total);
    return items;
  })();
  optionItemsCache.set(cacheKey, request);
  return request;
}

document.addEventListener("change", (event) => {
  if (event.target.matches("select.company-select")) {
    const selected = event.target.selectedOptions[0];
    const form = event.target.closest("form");
    const tenantInput = form?.querySelector("input[name='tenant_id']");
    if (tenantInput) tenantInput.value = selected?.dataset.tenantId || "";
  }
  if (event.target.matches("input.option-datalist")) {
    const hidden = document.querySelector(event.target.dataset.hiddenTarget);
    if (!hidden) return;
    const labelToId = JSON.parse(event.target.dataset.labelToId || "{}");
    hidden.value = labelToId[event.target.value] || "";
  }
});

function resetAjaxForm(form) {
  form.reset();
  form.dataset.method = "POST";
  form.dataset.api = form.dataset.createApi || form.dataset.api;
  form.querySelectorAll("input[type='hidden'][data-edit-id='true']").forEach((input) => input.remove());
  form.querySelectorAll("input[type='password']").forEach((input) => {
    input.value = "";
  });
}

function fillForm(form, data) {
  form.querySelectorAll("input[type='checkbox']").forEach((input) => {
    input.checked = false;
  });
  Object.entries(data).forEach(([key, value]) => {
    const input = form.elements[key];
    if (!input) return;
    if (input.type === "password") {
      input.value = "";
      return;
    }
    if (input instanceof RadioNodeList) {
      const values = Array.isArray(value) ? value.map(String) : [];
      Array.from(input).forEach((item) => {
        if (item.type === "checkbox") item.checked = values.includes(item.value);
      });
      return;
    }
    if (input.type === "checkbox") {
      input.checked = value === true || value === "true";
      return;
    }
    input.value = value ?? "";
  });
}

document.addEventListener("click", async (event) => {
  const addButton = event.target.closest("[data-create-modal]");
  if (addButton) {
    const modal = document.querySelector(addButton.dataset.createModal);
    const form = modal?.querySelector("form.ajax-form");
    if (form) resetAjaxForm(form);
    const title = modal?.querySelector(".modal-title");
    if (title) title.textContent = addButton.dataset.createTitle || "Add";
    return;
  }

  const viewButton = event.target.closest(".employee-view-button");
  if (viewButton) {
    const card = viewButton.closest(".employee-card");
    const body = document.getElementById("employeeViewBody");
    const modal = document.getElementById("employeeViewModal");
    if (!card || !body || !modal) return;
    const item = JSON.parse(decodeURIComponent(card.dataset.employee || "%7B%7D"));
    const modalInstance = new bootstrap.Modal(modal);
    body.innerHTML = `<div class="employee-card-empty">Loading employee details...</div>`;
    modalInstance.show();
    try {
      const [detail, assetResult, documents] = await Promise.all([
        apiFetch(`/api/employees/${item.id}`),
        apiFetch(`/api/assets?employee_id=${encodeURIComponent(item.id)}&page_size=100`).catch(() => ({items: []})),
        loadEmployeeDocuments(item.id).catch(() => []),
      ]);
      body.innerHTML = renderEmployeeView(item, detail, assetResult.items || [], documents);
    } catch (error) {
      body.innerHTML = `<div class="employee-card-empty">${escapeHtml(error.message || "Unable to load employee details")}</div>`;
    }
    return;
  }

  const docsButton = event.target.closest(".employee-documents-button");
  if (docsButton) {
    const card = docsButton.closest(".employee-card");
    if (!card) return;
    const item = JSON.parse(decodeURIComponent(card.dataset.employee || "%7B%7D"));
    await openEmployeeDocuments(item);
    return;
  }

  const editButton = event.target.closest(".table-edit-button");
  if (!editButton) return;
  try {
    const modal = document.querySelector(editButton.dataset.modal);
    const form = modal?.querySelector("form.ajax-form");
    if (!modal || !form) return;
    const data = await apiFetch(editButton.dataset.api);
    resetAjaxForm(form);
    form.dataset.method = "PUT";
    form.dataset.api = editButton.dataset.api;
    fillForm(form, data);
    const title = modal.querySelector(".modal-title");
    if (title) title.textContent = editButton.dataset.title;
    new bootstrap.Modal(modal).show();
  } catch (error) {
    toast(error.message || "Unable to load record", "danger");
  }
});

document.addEventListener("submit", async (event) => {
  try {
    if (event.target.id === "loginForm") {
      event.preventDefault();
      const body = formBody(event.target);
      await apiFetch("/api/auth/login", {method: "POST", body: JSON.stringify(body)});
      localStorage.removeItem("access_token");
      localStorage.removeItem("tenant_id");
      localStorage.removeItem("company_id");
      window.location.href = "/";
    }
    if (event.target.id === "employeeDocumentForm") {
      event.preventDefault();
      const employeeId = event.target.dataset.employeeId;
      const list = document.getElementById("employeeDocumentList");
      if (!employeeId) throw new Error("Employee is not selected");
      const body = new FormData(event.target);
      await apiFetch(`/api/employees/${employeeId}/documents`, {method: "POST", body});
      event.target.reset();
      if (list) {
        list.innerHTML = employeeDocumentList(await loadEmployeeDocuments(employeeId));
      }
      toast("Document uploaded");
      return;
    }
    if (event.target.classList.contains("ajax-form")) {
      event.preventDefault();
      const body = formBody(event.target);
      await apiFetch(event.target.dataset.api, {method: event.target.dataset.method || "POST", body: JSON.stringify(body)});
      toast("Saved");
      window.location.reload();
    }
    if (event.target.id === "attendanceForm") {
      event.preventDefault();
      const body = formBody(event.target);
      const result = await apiFetch("/api/attendance/check-in", {method: "POST", body: JSON.stringify(body)});
      toast(result.attendance_status === "approved" ? "Manual punch-in saved." : "Manual punch-in rejected.", result.attendance_status === "approved" ? "success" : "danger");
      bootstrap.Modal.getInstance(document.getElementById("manualPunchModal"))?.hide();
      const table = document.querySelector("#attendanceTable");
      if (table) hydrateDataTable(table);
    }
    if (event.target.id === "manualPunchOutForm") {
      event.preventDefault();
      const body = formBody(event.target);
      const result = await apiFetch("/api/attendance/manual-check-out", {method: "POST", body: JSON.stringify(body)});
      toast(`Manual punch-out saved. Worked ${result.total_work_minutes || 0} min`);
      bootstrap.Modal.getInstance(document.getElementById("manualPunchModal"))?.hide();
      const table = document.querySelector("#attendanceTable");
      if (table) hydrateDataTable(table);
    }
    if (event.target.classList.contains("table-filter-form")) {
      event.preventDefault();
      const table = document.querySelector(event.target.dataset.target);
      if (!table) return;
      const params = new URLSearchParams();
      Object.entries(formBody(event.target)).forEach(([key, value]) => {
        if (value !== "") params.set(key, value);
      });
      table.dataset.query = params.toString() ? `?${params.toString()}` : "";
      table.dataset.page = "1";
      hydrateDataTable(table);
    }
  } catch (error) {
    toast(error.message || "Request failed", "danger");
  }
});

document.addEventListener("reset", (event) => {
  if (event.target.classList.contains("report-export-form")) {
    window.setTimeout(() => {
      event.target.querySelectorAll("input[type='hidden']").forEach((input) => {
        input.value = "";
      });
    }, 0);
    return;
  }
  if (!event.target.classList.contains("table-filter-form")) return;
  window.setTimeout(() => {
    const table = document.querySelector(event.target.dataset.target);
    if (!table) return;
    table.dataset.query = "";
    table.dataset.page = "1";
    hydrateDataTable(table);
  }, 0);
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
    const path = new URL(link.href, window.location.origin).pathname;
    const current = window.location.pathname;
    if (path === current || (path !== "/" && current.startsWith(path))) {
      link.classList.add("active");
    }
  });
  loadSelectOptions();
  loadDatalistOptions();
  const summary = document.getElementById("myAttendanceSummary");
  if (summary) {
    apiFetch("/api/attendance/me/today").then((data) => {
      const attendance = data.attendance;
      const shift = `${data.shift_name} (${data.shift_start}-${data.shift_end})`;
      summary.textContent = attendance
        ? `${data.employee_name} | ${shift} | ${attendance.check_in_status} | ${attendance.check_out_status} | ${attendance.total_work_minutes} min`
        : `${data.employee_name} | ${shift} | Not punched in yet`;
    }).catch(() => {
      summary.textContent = "Employee profile, branch, and shift assignment are required for punch in/out.";
    });
  }
  document.getElementById("punchInButton")?.addEventListener("click", () => {
    currentLocationPayload(async (body) => {
      const result = await apiFetch("/api/attendance/punch-in", {method: "POST", body: JSON.stringify(body)});
      toast(`Punch in ${result.check_in_status}. Distance ${result.distance_from_office}m`);
      window.location.reload();
    });
  });
  document.getElementById("punchOutButton")?.addEventListener("click", () => {
    currentLocationPayload(async (body) => {
      const result = await apiFetch("/api/attendance/punch-out", {method: "POST", body: JSON.stringify(body)});
      toast(`Punch out ${result.check_out_status}. Worked ${result.total_work_minutes} min`);
      window.location.reload();
    });
  });
  document.querySelectorAll(".data-table").forEach((table) => hydrateDataTable(table));
});

function setText(selector, value) {
  document.querySelectorAll(selector).forEach((el) => {
    el.textContent = value ?? "--";
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function statusBadge(label) {
  const normalized = String(label || "").toLowerCase();
  const tone = normalized.includes("active") || normalized.includes("approved") || normalized.includes("on time")
    ? "success"
    : normalized.includes("late") || normalized.includes("pending") || normalized.includes("half") || normalized.includes("auto")
      ? "warning"
      : normalized.includes("reject") || normalized.includes("missing") || normalized.includes("no punches")
        ? "danger"
        : "neutral";
  return `<span class="status-badge status-badge-${tone}">${escapeHtml(label || "Needs review")}</span>`;
}

function renderEmpty(target, message) {
  target.innerHTML = `<div class="empty-state">${message}</div>`;
}

function renderDashboardTrend(data) {
  const canvas = document.getElementById("attendanceTrendChart");
  if (!canvas || !window.Chart) return;
  const labels = data.trend.map((item) => item.label);
  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Present",
          data: data.trend.map((item) => item.present),
          borderColor: "#3ecf8e",
          backgroundColor: "rgba(62, 207, 142, .08)",
          fill: true,
          tension: .35,
        },
        {
          label: "Late / Half Day",
          data: data.trend.map((item) => item.late),
          borderColor: "#f5b244",
          tension: .35,
        },
        {
          label: "Rejected",
          data: data.trend.map((item) => item.rejected),
          borderColor: "#f26b6b",
          tension: .35,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {legend: {position: "bottom", labels: {boxWidth: 10, boxHeight: 10, color: "#8b8d9a"}}},
      scales: {
        y: {beginAtZero: true, ticks: {precision: 0, color: "#8b8d9a"}, grid: {color: "rgba(255,255,255,.07)"}},
        x: {ticks: {color: "#8b8d9a"}, grid: {display: false}},
      },
    },
  });
}

function renderDashboardLists(data) {
  const exceptions = document.getElementById("exceptionList");
  if (exceptions) {
    if (!data.exceptions.length) {
      renderEmpty(exceptions, "No attendance exceptions for today.");
    } else {
      exceptions.innerHTML = data.exceptions.map((item) => `
        <a class="action-item" href="/attendance">
          <div>
            <strong>${escapeHtml(item.employee)}</strong>
            <span>${escapeHtml(item.branch)}</span>
          </div>
          <div class="action-item__meta">
            ${statusBadge(item.issue || item.status)}
          </div>
        </a>
      `).join("");
    }
  }

  const branches = document.getElementById("branchHealthList");
  if (branches) {
    if (!data.branch_health.length) {
      renderEmpty(branches, "No branches configured yet.");
    } else {
      branches.innerHTML = data.branch_health.map((item) => `
        <div class="branch-health-item">
          <div class="branch-health-item__main">
            <strong>${escapeHtml(item.name)}</strong>
            <span>${escapeHtml(item.present)}/${escapeHtml(item.employees)} present</span>
          </div>
          <div class="branch-health-item__bar">
            <span style="width:${Math.max(0, Math.min(100, Number(item.coverage) || 0))}%"></span>
          </div>
          ${statusBadge(item.status)}
        </div>
      `).join("");
    }
  }

  const gaps = document.getElementById("setupGapList");
  if (gaps) {
    if (!data.setup_gaps.length) {
      renderEmpty(gaps, "Configuration is complete for the current scope.");
    } else {
      gaps.innerHTML = data.setup_gaps.map((item) => `
        <a class="action-item" href="${escapeHtml(item.href)}">
          <div>
            <strong>${escapeHtml(item.label)}</strong>
            <span>${escapeHtml(item.meta)}</span>
          </div>
          ${statusBadge("Missing")}
        </a>
      `).join("");
    }
  }
}

async function renderDashboard() {
  try {
    const data = await apiFetch("/api/dashboard/summary");
    const formattedDate = new Date(`${data.date}T00:00:00`).toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    setText("#dashboardDate", formattedDate);
    Object.entries(data.metrics).forEach(([key, value]) => {
      setText(`[data-dashboard-metric="${key}"]`, value);
    });
    setText("#facesEnrolled", data.enrollment.enrolled);
    setText("#facesMissing", data.enrollment.missing);
    const coverageBar = document.getElementById("faceCoverageBar");
    if (coverageBar) coverageBar.style.width = `${data.enrollment.coverage}%`;
    renderDashboardTrend(data);
    renderDashboardLists(data);
  } catch (error) {
    toast(error.message || "Unable to load dashboard", "danger");
    document.querySelectorAll(".action-list, .branch-health-list").forEach((target) => {
      renderEmpty(target, "Unable to load this panel.");
    });
  }
}

function renderBranchMap() {
  const el = document.getElementById("branchMap");
  if (!el) return;
  const map = L.map(el).setView([20.5937, 78.9629], 5);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19}).addTo(map);
}
