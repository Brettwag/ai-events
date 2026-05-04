const state = {
  runtime: null,
  sources: [],
  candidates: [],
  workflows: [],
  reviewRows: [],
  reviewSort: loadReviewSort(),
  reviewColumnOrder: loadReviewColumnOrder(),
  reviewLaneStats: [],
  publicIcsFeedUrl: "",
  activeColumnMenu: null,
  dragColumnId: null,
};

let statusResetTimer = null;

const reviewColumns = [
  { id: "event", label: "Event", cellClass: "cell-title review-event", render: renderEventCell, sortValue: sortValueEvent },
  { id: "timing", label: "Timing", render: renderTimingCell, sortValue: sortValueTiming },
  { id: "location", label: "Location", render: renderLocationCell, sortValue: sortValueLocation },
  { id: "source", label: "Source", render: renderSourceCell, sortValue: sortValueSource },
  { id: "quality", label: "Quality", render: renderQualityCell, sortValue: sortValueQuality },
  { id: "notes", label: "Notes", cellClass: "review-notes-cell", render: renderNotesCell, sortValue: sortValueNotes },
  { id: "review", label: "Review", cellClass: "review-cell", render: renderReviewCell, sortValue: sortValueReview },
];

const reviewColumnMap = new Map(reviewColumns.map((column) => [column.id, column]));

const runtimeFieldSpec = [
  ["project.name", "Project Name", "text"],
  ["project.time_zone", "Time Zone", "text"],
  ["project.run_time_local", "Run Time", "text"],
  ["pilot.radius_miles_min", "Min Radius", "number"],
  ["pilot.radius_miles_max", "Max Radius", "number"],
  ["quality.lookahead_days", "Lookahead Days", "number"],
  ["ai_event_scout.max_events_per_run", "AI Event Target", "number"],
  ["ai_event_scout.max_passes", "AI Event Max Passes", "number"],
  ["ai_event_scout.stop_after_consecutive_empty_passes", "AI Scout Empty Stop", "number"],
  ["source_scout.max_candidates_per_run", "Source Scout Target", "number"],
  ["ai_event_scout.minimum_trust_level", "AI Trust Floor", "select", ["low", "medium", "high"]],
  ["project.review_sheet_name", "Main Queue Sheet", "text"],
  ["project.source_scout_sheet_name", "Source Scout Sheet", "text"],
  ["project.ai_event_scout_sheet_name", "AI Event Sheet", "text"],
  ["pilot.geography", "Geography", "list"],
  ["ai_event_scout.query_focuses", "AI Event Focuses", "list"],
  ["ai_event_scout.source_type_focuses", "Source Type Focuses", "list"],
  ["source_scout.approved_domains", "Approved Domains", "list"],
  ["pilot.geography_notes", "Geography Notes", "textarea"],
];

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

document.getElementById("save-runtime").addEventListener("click", saveRuntime);
document.getElementById("save-sources").addEventListener("click", saveSources);
document.getElementById("add-source").addEventListener("click", () => {
  state.sources.push(blankSource());
  renderSources();
});
document.getElementById("save-review").addEventListener("click", saveReviews);
document.getElementById("refresh-review").addEventListener("click", refreshReviewRows);
document.getElementById("copy-ics-url").addEventListener("click", copyIcsUrl);
document.addEventListener("click", handleGlobalClick);

bootstrap();

async function bootstrap() {
  setStatus("Loading workspace", { tone: "loading", temporary: false });
  try {
    await Promise.all([loadRuntime(), loadSources(), loadCandidates(), loadWorkflows()]);
    setIcsFeedUrl();
    renderRuntime();
    renderSources();
    renderCandidates();
    renderWorkflows();
    await refreshReviewRows({ silent: true });
    resetStatus();
  } catch (error) {
    setStatus(error.message || "Workspace unavailable", { tone: "error", temporary: false });
  }
}

async function loadRuntime() {
  state.runtime = await fetchJson("/api/runtime");
}

async function loadSources() {
  const payload = await fetchJson("/api/sources");
  state.sources = payload.sources;
}

async function loadCandidates() {
  const payload = await fetchJson("/api/source-candidates");
  state.candidates = payload.candidates;
}

async function loadWorkflows() {
  const payload = await fetchJson("/api/workflows");
  state.workflows = payload.workflows;
}

async function refreshReviewRows({ silent = false } = {}) {
  const button = document.getElementById("refresh-review");
  setButtonBusy(button, true);
  if (!silent) {
    setStatus("Refreshing review queue", { tone: "loading", temporary: false });
  }
  try {
    const payload = await fetchJson("/api/review-queue?sort=date");
    state.reviewRows = payload.rows || [];
    state.reviewLaneStats = payload.lane_stats || [];
    state.publicIcsFeedUrl = payload.public_ics_feed_url || "";
    setIcsFeedUrl();
    renderReview();
    if (!silent) {
      setStatus("Review refreshed", { tone: "success" });
    }
  } catch (error) {
    state.reviewRows = [];
    state.reviewLaneStats = [];
    renderReviewError(error.message);
    if (!silent) {
      setStatus(error.message || "Review unavailable", { tone: "error" });
    }
  } finally {
    setButtonBusy(button, false);
  }
}

function activateView(view) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
  document.getElementById("view-title").textContent = {
    inputs: "Inputs",
    review: "Review",
    sources: "Approved Sources",
    candidates: "Candidate Sources",
    workflows: "Workflows",
  }[view];
}

function renderRuntime() {
  const form = document.getElementById("runtime-form");
  form.innerHTML = "";
  runtimeFieldSpec.forEach(([path, label, type, options]) => {
    const field = document.createElement("div");
    field.className = "field";
    if (type === "textarea" || type === "list") {
      field.classList.add("full");
    }
    const labelEl = document.createElement("label");
    labelEl.textContent = label;
    field.appendChild(labelEl);

    let input;
    const value = getPath(state.runtime, path);
    if (type === "textarea") {
      input = document.createElement("textarea");
      input.value = value ?? "";
    } else if (type === "select") {
      input = document.createElement("select");
      options.forEach((optionValue) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        option.selected = optionValue === value;
        input.appendChild(option);
      });
    } else if (type === "list") {
      input = document.createElement("textarea");
      input.value = Array.isArray(value) ? value.join("\n") : "";
    } else {
      input = document.createElement("input");
      input.type = type;
      input.value = value ?? "";
    }
    input.dataset.path = path;
    input.dataset.kind = type;
    field.appendChild(input);
    form.appendChild(field);
  });
}

function renderReview() {
  closeColumnMenu();
  renderReviewSummary();
  renderReviewLanes();
  renderReviewSortIndicator();
  const container = document.getElementById("review-list");
  container.innerHTML = "";

  if (!state.reviewRows.length) {
    container.innerHTML = `<div class="empty">No event rows are available from the workflow sheets yet.</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "data-table review-table";
  table.innerHTML = `
    <thead>
      <tr>
        ${orderedReviewColumns().map((column) => reviewHeaderCell(column)).join("")}
      </tr>
    </thead>
    <tbody>
      ${sortedReviewRows().map((row) => reviewRow(row)).join("")}
    </tbody>
  `;
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "table-wrap review-scroll-wrap";
  scrollWrap.appendChild(table);
  container.appendChild(scrollWrap);
  wireReviewHeaderInteractions(container);

  container.querySelectorAll("[data-review-status]").forEach((input) => {
    input.addEventListener("change", handleReviewFieldChange);
  });
  container.querySelectorAll("[data-review-notes]").forEach((input) => {
    input.addEventListener("input", handleReviewFieldChange);
  });
}

function renderReviewError(message) {
  renderReviewSummary();
  renderReviewLanes();
  renderReviewSortIndicator();
  document.getElementById("review-list").innerHTML = `<div class="empty error-block">${escapeHtml(message)}</div>`;
}

function renderReviewSummary() {
  const container = document.getElementById("review-summary");
  const counts = countReviews();
  container.innerHTML = `
    <span class="meta-pill">${state.reviewRows.length} total</span>
    <span class="meta-pill review-status-pill review-status-pending">${counts.pending} pending</span>
    <span class="meta-pill review-status-pill review-status-approved">${counts.approved} approved</span>
    <span class="meta-pill review-status-pill review-status-needs-edit">${counts.needsEdit} needs edit</span>
    <span class="meta-pill review-status-pill review-status-rejected">${counts.rejected} rejected</span>
  `;
}

function renderReviewLanes() {
  const container = document.getElementById("review-lanes");
  container.innerHTML = state.reviewLaneStats
    .map(
      (lane) =>
        `<span class="meta-pill">${escapeHtml(lane.label)}: ${escapeHtml(String(lane.event_rows))}</span>`
    )
    .join("");
}

function renderSources() {
  const container = document.getElementById("sources-list");
  container.innerHTML = "";
  if (!state.sources.length) {
    container.innerHTML = `<div class="empty">No approved sources yet.</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Source</th>
        <th>Status</th>
        <th>Organization</th>
        <th>Base URL</th>
        <th>Seed URLs</th>
        <th>Mode</th>
        <th>Geography</th>
        <th>Notes</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      ${state.sources.map((source, index) => sourceRow(source, index)).join("")}
    </tbody>
  `;
  container.appendChild(table);

  container.querySelectorAll("[data-remove-source]").forEach((button) => {
    button.addEventListener("click", () => {
      state.sources.splice(Number(button.dataset.removeSource), 1);
      renderSources();
    });
  });
}

function renderCandidates() {
  const container = document.getElementById("candidate-list");
  container.innerHTML = "";
  if (!state.candidates.length) {
    container.innerHTML = `<div class="empty">No candidate sources yet.</div>`;
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Source</th>
        <th>Status</th>
        <th>Priority</th>
        <th>Type</th>
        <th>Base URL</th>
        <th>Seed URL</th>
        <th>Geography</th>
        <th>Parser</th>
      </tr>
    </thead>
    <tbody>
      ${state.candidates.map((candidate) => candidateRow(candidate)).join("")}
    </tbody>
  `;
  container.appendChild(table);
}

function renderWorkflows() {
  const container = document.getElementById("workflow-list");
  container.innerHTML = "";
  state.workflows.forEach((workflow) => {
    const card = document.createElement("div");
    card.className = "workflow-card";
    card.innerHTML = `
      <h3>${escapeHtml(workflow.name)}</h3>
      <p>${escapeHtml(workflow.purpose)}</p>
      <div class="meta-row">
        <span class="meta-pill">${escapeHtml(workflow.id)}</span>
        <span class="meta-pill">${escapeHtml(workflow.sheet)}</span>
        <span class="meta-pill">Active lane</span>
      </div>
    `;
    container.appendChild(card);
  });
}

async function saveRuntime() {
  const button = document.getElementById("save-runtime");
  setButtonBusy(button, true);
  setStatus("Saving inputs", { tone: "loading", temporary: false });
  const payload = structuredClone(state.runtime);
  try {
    document.querySelectorAll("#runtime-form [data-path]").forEach((input) => {
      const kind = input.dataset.kind;
      let value = input.value;
      if (kind === "number") {
        value = Number(value);
      } else if (kind === "list") {
        value = value.split("\n").map((item) => item.trim()).filter(Boolean);
      }
      setPath(payload, input.dataset.path, value);
    });
    await postJson("/api/runtime", payload);
    state.runtime = payload;
    setStatus("Inputs saved", { tone: "success" });
  } catch (error) {
    setStatus(error.message || "Inputs failed to save", { tone: "error" });
  } finally {
    setButtonBusy(button, false);
  }
}

async function saveSources() {
  const button = document.getElementById("save-sources");
  setButtonBusy(button, true);
  setStatus("Saving sources", { tone: "loading", temporary: false });
  try {
    const sources = Array.from(document.querySelectorAll("[data-source-index]")).reduce((acc, input) => {
      const index = Number(input.dataset.sourceIndex);
      acc[index] ||= structuredClone(state.sources[index]);
      let value = input.value;
      if (input.dataset.key === "enabled") {
        value = value === "true";
      } else if (input.dataset.key === "seed_urls" || input.dataset.key === "geography_tags") {
        value = value.split("\n").map((item) => item.trim()).filter(Boolean);
      }
      acc[index][input.dataset.key] = value;
      return acc;
    }, []);
    state.sources = sources;
    await postJson("/api/sources", { sources });
    setStatus("Sources saved", { tone: "success" });
  } catch (error) {
    setStatus(error.message || "Sources failed to save", { tone: "error" });
  } finally {
    setButtonBusy(button, false);
  }
}

async function saveReviews() {
  const button = document.getElementById("save-review");
  setButtonBusy(button, true);
  setStatus("Saving reviews", { tone: "loading", temporary: false });
  try {
    syncReviewRowsFromDom();
    const updates = state.reviewRows.map((row) => ({
      record_id: row.record_id,
      sheet_name: row.sheet_name,
      review_status: row.review_status,
      approved_for_export: row.review_status === "Approved",
      reviewer_notes: row.reviewer_notes,
    }));
    await postJson("/api/review-queue", { updates });
    await refreshReviewRows({ silent: true });
    setStatus("Reviews saved", { tone: "success" });
  } catch (error) {
    setStatus(error.message || "Reviews failed to save", { tone: "error" });
  } finally {
    setButtonBusy(button, false);
  }
}

function handleReviewFieldChange() {
  syncReviewRowsFromDom();
  renderReviewSummary();
  syncReviewSelectClasses();
}

function syncReviewRowsFromDom() {
  document.querySelectorAll("[data-review-key]").forEach((row) => {
    const key = row.dataset.reviewKey;
    const statusInput = row.querySelector("[data-review-status]");
    const notesInput = row.querySelector("[data-review-notes]");
    const target = state.reviewRows.find((item) => reviewRowKey(item) === key);
    if (!target) {
      return;
    }
    target.review_status = statusInput.value;
    target.approved_for_export = statusInput.value === "Approved";
    target.reviewer_notes = notesInput.value;
  });
}

function syncReviewSelectClasses() {
  document.querySelectorAll("[data-review-status]").forEach((input) => {
    input.classList.remove(
      "review-status-pending",
      "review-status-approved",
      "review-status-needs-edit",
      "review-status-rejected"
    );
    input.classList.add(reviewStatusClass(input.value));
  });
}

function sourceInput(index, key, value, type = "text") {
  if (type === "select") {
    return `
      <select class="table-select" data-source-index="${index}" data-key="${key}">
          <option value="true" ${value === "true" ? "selected" : ""}>Enabled</option>
          <option value="false" ${value !== "true" ? "selected" : ""}>Disabled</option>
      </select>
    `;
  }
  return `<input class="table-input" data-source-index="${index}" data-key="${key}" value="${escapeHtml(value || "")}" />`;
}

function blankSource() {
  return {
    id: "",
    label: "",
    enabled: true,
    type: "website",
    discovery_mode: "listing_page",
    base_url: "",
    seed_urls: [],
    source_organization: "",
    geography_tags: [],
    notes: "",
  };
}

function getPath(object, path) {
  return path.split(".").reduce((acc, key) => acc?.[key], object);
}

function setPath(object, path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  const target = keys.reduce((acc, key) => acc[key], object);
  target[last] = value;
}

function setStatus(message, { tone = "neutral", temporary = true } = {}) {
  const pill = document.getElementById("save-status");
  clearTimeout(statusResetTimer);
  pill.textContent = message;
  pill.classList.remove("is-neutral", "is-loading", "is-success", "is-error");
  pill.classList.add(`is-${tone}`);
  if (temporary) {
    statusResetTimer = setTimeout(() => {
      resetStatus();
    }, tone === "error" ? 3200 : 2200);
  }
}

function resetStatus() {
  const pill = document.getElementById("save-status");
  clearTimeout(statusResetTimer);
  pill.textContent = "Ready";
  pill.classList.remove("is-loading", "is-success", "is-error");
  pill.classList.add("is-neutral");
}

function setButtonBusy(button, busy) {
  if (!button) return;
  button.disabled = busy;
  button.dataset.busy = busy ? "true" : "false";
}

function setIcsFeedUrl() {
  const input = document.getElementById("ics-feed-url");
  input.value = state.publicIcsFeedUrl || `${window.location.origin}/api/approved-events.ics`;
}

async function copyIcsUrl() {
  const button = document.getElementById("copy-ics-url");
  setButtonBusy(button, true);
  const input = document.getElementById("ics-feed-url");
  input.select();
  input.setSelectionRange(0, input.value.length);
  try {
    await navigator.clipboard.writeText(input.value);
    setStatus("ICS URL copied", { tone: "success" });
  } catch {
    document.execCommand("copy");
    setStatus("ICS URL copied", { tone: "success" });
  } finally {
    setButtonBusy(button, false);
  }
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `${url} failed`);
  }
  return data;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `${url} failed`);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function reviewRow(row) {
  const orderedColumns = orderedReviewColumns();
  return `
    <tr data-review-key="${escapeHtml(reviewRowKey(row))}">
      ${orderedColumns.map((column) => `<td class="${escapeHtml(column.cellClass || "")}">${column.render(row)}</td>`).join("")}
    </tr>
  `;
}

function renderEventCell(row) {
  return `
    <div class="cell-stack">
      <strong>${escapeHtml(row.event_title || "Untitled event")}</strong>
      <div class="tag-list">
        <span class="meta-pill">${escapeHtml(row.record_id)}</span>
        <span class="meta-pill">${escapeHtml(row.queue_label)}</span>
      </div>
    </div>
  `;
}

function renderTimingCell(row) {
  return `
    <div class="cell-stack">
      <strong>${escapeHtml(formatDateRange(row))}</strong>
      <div class="cell-subtitle">${escapeHtml(formatTimeRange(row))}</div>
    </div>
  `;
}

function renderLocationCell(row) {
  return `
    <div class="cell-stack">
      <strong>${escapeHtml(row.venue_name || "Location pending")}</strong>
      <div class="cell-subtitle">${escapeHtml(formatLocation(row))}</div>
    </div>
  `;
}

function renderSourceCell(row) {
  return `
    <div class="cell-stack">
      <strong>${escapeHtml(row.source_name || "Unknown source")}</strong>
      <div class="cell-subtitle">${escapeHtml(row.source_method)}</div>
      <div class="review-links">
        ${row.source_url ? `<a href="${escapeHtml(row.source_url)}" target="_blank" rel="noreferrer">Source</a>` : ""}
        ${row.event_url ? `<a href="${escapeHtml(row.event_url)}" target="_blank" rel="noreferrer">Event</a>` : ""}
      </div>
    </div>
  `;
}

function renderQualityCell(row) {
  return `
    <div class="cell-stack">
      <div class="tag-list">
        <span class="meta-pill">${escapeHtml(row.trust_level || "unrated")}</span>
        <span class="meta-pill">${escapeHtml(row.confidence_score ? `Score ${row.confidence_score}` : "Score n/a")}</span>
      </div>
      <div class="tag-list">
        ${row.missing_fields.map((item) => `<span class="meta-pill meta-pill-warn">${escapeHtml(item)}</span>`).join("")}
        ${row.risk_flags.map((item) => `<span class="meta-pill meta-pill-risk">${escapeHtml(item)}</span>`).join("")}
      </div>
    </div>
  `;
}

function renderNotesCell(row) {
  return `<textarea class="table-textarea review-notes" data-review-notes placeholder="Reviewer notes">${escapeHtml(row.reviewer_notes || "")}</textarea>`;
}

function renderReviewCell(row) {
  return `
    <div class="cell-stack">
      <div class="review-select-wrap ${reviewStatusClass(row.review_status)}">
        <select class="table-select review-select ${reviewStatusClass(row.review_status)}" data-review-status>
          ${reviewStatusOptions(row.review_status)}
        </select>
      </div>
      <div class="cell-subtitle review-helper-text">Approved rows export automatically.</div>
    </div>
  `;
}

function reviewHeaderCell(column) {
  const sortState = state.reviewSort.columnId === column.id ? state.reviewSort.direction : "";
  const sortIcon = sortState === "asc" ? "↑" : sortState === "desc" ? "↓" : "";
  return `
    <th draggable="true" data-column-id="${escapeHtml(column.id)}" class="review-th ${state.dragColumnId === column.id ? "dragging" : ""}">
      <div class="review-header-cell">
        <button type="button" class="review-header-button" data-column-menu-trigger="${escapeHtml(column.id)}">
          <span>${escapeHtml(column.label)}</span>
          <span class="review-header-sort">${escapeHtml(sortIcon)}</span>
        </button>
      </div>
    </th>
  `;
}

function reviewStatusOptions(selectedValue) {
  const statuses = state.runtime?.review?.allowed_statuses || ["Pending", "Approved", "Rejected", "Needs Edit"];
  return statuses
    .map((status) => `<option value="${escapeHtml(status)}" ${status === selectedValue ? "selected" : ""}>${escapeHtml(status)}</option>`)
    .join("");
}

function reviewStatusClass(status) {
  if (status === "Approved") return "review-status-approved";
  if (status === "Rejected") return "review-status-rejected";
  if (status === "Needs Edit") return "review-status-needs-edit";
  return "review-status-pending";
}

function orderedReviewColumns() {
  const validIds = state.reviewColumnOrder.filter((id) => reviewColumnMap.has(id));
  const missingIds = reviewColumns.map((column) => column.id).filter((id) => !validIds.includes(id));
  return [...validIds, ...missingIds].map((id) => reviewColumnMap.get(id));
}

function sortedReviewRows() {
  const rows = [...state.reviewRows];
  const { columnId, direction } = state.reviewSort;
  const column = reviewColumnMap.get(columnId) || reviewColumnMap.get("timing");
  const multiplier = direction === "desc" ? -1 : 1;
  rows.sort((left, right) => compareSortValues(column.sortValue(left), column.sortValue(right)) * multiplier);
  return rows;
}

function compareSortValues(left, right) {
  const a = Array.isArray(left) ? left : [left];
  const b = Array.isArray(right) ? right : [right];
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const leftValue = String(a[index] ?? "");
    const rightValue = String(b[index] ?? "");
    if (leftValue < rightValue) return -1;
    if (leftValue > rightValue) return 1;
  }
  return 0;
}

function sortValueEvent(row) {
  return [row.event_title?.toLowerCase() || "", row.start_date || "", row.source_name?.toLowerCase() || ""];
}

function sortValueTiming(row) {
  return [row.start_date || "9999-99-99", normalizeTimeForSort(row.start_time), row.event_title?.toLowerCase() || ""];
}

function sortValueLocation(row) {
  return [row.venue_name?.toLowerCase() || "", row.city?.toLowerCase() || "", row.event_title?.toLowerCase() || ""];
}

function sortValueSource(row) {
  return [row.source_name?.toLowerCase() || "", row.start_date || "9999-99-99", row.event_title?.toLowerCase() || ""];
}

function sortValueQuality(row) {
  return [row.trust_level?.toLowerCase() || "", String(row.confidence_score || ""), row.event_title?.toLowerCase() || ""];
}

function sortValueNotes(row) {
  return [row.reviewer_notes?.toLowerCase() || "", row.event_title?.toLowerCase() || ""];
}

function sortValueReview(row) {
  return [row.review_status?.toLowerCase() || "", row.event_title?.toLowerCase() || ""];
}

function normalizeTimeForSort(value) {
  const text = String(value || "").trim();
  if (!text) return "99:99:99";
  const normalized = text.toLowerCase().replace(/\./g, "").replace(/a m/g, "am").replace(/p m/g, "pm");
  let match = normalized.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (match) {
    return `${match[1].padStart(2, "0")}:${match[2]}:${(match[3] || "00").padStart(2, "0")}`;
  }
  match = normalized.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$/);
  if (!match) {
    match = normalized.match(/^(\d{1,2})(am|pm)$/);
    if (match) {
      const hour = Number(match[1]) % 12 + (match[2] === "pm" ? 12 : 0);
      return `${String(hour).padStart(2, "0")}:00:00`;
    }
    return text;
  }
  let hour = Number(match[1]) % 12;
  if (match[3] === "pm") hour += 12;
  const minute = match[2] || "00";
  return `${String(hour).padStart(2, "0")}:${minute}:00`;
}

function reviewRowKey(row) {
  return `${row.sheet_name}::${row.record_id}`;
}

function renderReviewSortIndicator() {
  const indicator = document.getElementById("review-sort-indicator");
  const column = reviewColumnMap.get(state.reviewSort.columnId) || reviewColumnMap.get("timing");
  const direction = state.reviewSort.direction === "desc" ? "descending" : "ascending";
  indicator.textContent = `Sorted by ${column.label.toLowerCase()} (${direction})`;
}

function wireReviewHeaderInteractions(container) {
  container.querySelectorAll("[data-column-menu-trigger]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const columnId = button.dataset.columnMenuTrigger;
      toggleColumnMenu(columnId, button);
    });
  });

  container.querySelectorAll("[data-column-id]").forEach((header) => {
    header.addEventListener("dragstart", handleColumnDragStart);
    header.addEventListener("dragover", handleColumnDragOver);
    header.addEventListener("drop", handleColumnDrop);
    header.addEventListener("dragend", handleColumnDragEnd);
  });
}

function handleColumnDragStart(event) {
  state.dragColumnId = event.currentTarget.dataset.columnId;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", state.dragColumnId);
  requestAnimationFrame(() => event.currentTarget.classList.add("is-dragging"));
}

function handleColumnDragOver(event) {
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
}

function handleColumnDrop(event) {
  event.preventDefault();
  const targetId = event.currentTarget.dataset.columnId;
  const draggedId = event.dataTransfer.getData("text/plain") || state.dragColumnId;
  moveColumnToTarget(draggedId, targetId);
}

function handleColumnDragEnd(event) {
  event.currentTarget.classList.remove("is-dragging");
  state.dragColumnId = null;
}

function moveColumnToTarget(draggedId, targetId) {
  if (!draggedId || !targetId || draggedId === targetId) return;
  const order = [...orderedReviewColumns().map((column) => column.id)];
  const fromIndex = order.indexOf(draggedId);
  const toIndex = order.indexOf(targetId);
  if (fromIndex === -1 || toIndex === -1) return;
  order.splice(fromIndex, 1);
  order.splice(toIndex, 0, draggedId);
  state.reviewColumnOrder = order;
  persistReviewColumnOrder();
  closeColumnMenu();
  renderReview();
}

function toggleColumnMenu(columnId, trigger) {
  if (state.activeColumnMenu?.columnId === columnId) {
    closeColumnMenu();
    return;
  }
  state.activeColumnMenu = { columnId };
  renderColumnMenu(columnId, trigger);
}

function renderColumnMenu(columnId, trigger) {
  const menu = document.getElementById("review-column-menu");
  const columns = orderedReviewColumns();
  const index = columns.findIndex((column) => column.id === columnId);
  const column = reviewColumnMap.get(columnId);
  if (!menu || !column || index === -1) return;

  menu.innerHTML = `
    <button type="button" class="column-menu-item" data-column-action="sort-asc" data-column-id="${escapeHtml(columnId)}">↑ Sort ascending</button>
    <button type="button" class="column-menu-item" data-column-action="sort-desc" data-column-id="${escapeHtml(columnId)}">↓ Sort descending</button>
    <button type="button" class="column-menu-item" data-column-action="move-left" data-column-id="${escapeHtml(columnId)}" ${index === 0 ? "disabled" : ""}>← Move left</button>
    <button type="button" class="column-menu-item" data-column-action="move-right" data-column-id="${escapeHtml(columnId)}" ${index === columns.length - 1 ? "disabled" : ""}>→ Move right</button>
  `;
  const rect = trigger.getBoundingClientRect();
  menu.style.left = `${window.scrollX + rect.left}px`;
  menu.style.top = `${window.scrollY + rect.bottom + 6}px`;
  menu.hidden = false;

  menu.querySelectorAll("[data-column-action]").forEach((button) => {
    button.addEventListener("click", handleColumnMenuAction);
  });
}

function handleColumnMenuAction(event) {
  const button = event.currentTarget;
  const action = button.dataset.columnAction;
  const columnId = button.dataset.columnId;
  if (action === "sort-asc" || action === "sort-desc") {
    state.reviewSort = { columnId, direction: action === "sort-desc" ? "desc" : "asc" };
    persistReviewSort();
    closeColumnMenu();
    renderReview();
    return;
  }
  if (action === "move-left") {
    nudgeColumn(columnId, -1);
    return;
  }
  if (action === "move-right") {
    nudgeColumn(columnId, 1);
  }
}

function nudgeColumn(columnId, delta) {
  const order = [...orderedReviewColumns().map((column) => column.id)];
  const index = order.indexOf(columnId);
  const nextIndex = index + delta;
  if (index === -1 || nextIndex < 0 || nextIndex >= order.length) return;
  [order[index], order[nextIndex]] = [order[nextIndex], order[index]];
  state.reviewColumnOrder = order;
  persistReviewColumnOrder();
  closeColumnMenu();
  renderReview();
}

function closeColumnMenu() {
  const menu = document.getElementById("review-column-menu");
  if (menu) {
    menu.hidden = true;
    menu.innerHTML = "";
  }
  state.activeColumnMenu = null;
}

function handleGlobalClick(event) {
  const menu = document.getElementById("review-column-menu");
  if (!menu || menu.hidden) return;
  if (menu.contains(event.target)) return;
  if (event.target.closest("[data-column-menu-trigger]")) return;
  closeColumnMenu();
}

function loadReviewColumnOrder() {
  try {
    const value = JSON.parse(window.localStorage.getItem("reviewColumnOrder") || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function persistReviewColumnOrder() {
  window.localStorage.setItem("reviewColumnOrder", JSON.stringify(state.reviewColumnOrder));
}

function loadReviewSort() {
  try {
    const value = JSON.parse(window.localStorage.getItem("reviewSort") || "{}");
    if (value && typeof value.columnId === "string" && typeof value.direction === "string") {
      return value;
    }
  } catch {}
  return { columnId: "timing", direction: "asc" };
}

function persistReviewSort() {
  window.localStorage.setItem("reviewSort", JSON.stringify(state.reviewSort));
}

function formatDateRange(row) {
  if (row.end_date && row.end_date !== row.start_date) {
    return `${row.start_date} to ${row.end_date}`;
  }
  return row.start_date || "Date missing";
}

function formatTimeRange(row) {
  if (row.start_time && row.end_time) {
    return `${row.start_time} to ${row.end_time}`;
  }
  if (row.start_time) {
    return row.start_time;
  }
  return "Time missing";
}

function formatLocation(row) {
  return [row.address, row.city, row.state].filter(Boolean).join(", ") || "Address needs review";
}

function countReviews() {
  return state.reviewRows.reduce(
    (counts, row) => {
      const status = row.review_status || "Pending";
      if (status === "Approved") counts.approved += 1;
      else if (status === "Rejected") counts.rejected += 1;
      else if (status === "Needs Edit") counts.needsEdit += 1;
      else counts.pending += 1;
      return counts;
    },
    { pending: 0, approved: 0, rejected: 0, needsEdit: 0 }
  );
}

function sourceRow(source, index) {
  return `
    <tr>
      <td class="cell-title">
        <div class="cell-stack">
          <strong>${escapeHtml(source.label || "Untitled source")}</strong>
          ${sourceInput(index, "label", source.label)}
          <div class="cell-subtitle">ID: ${escapeHtml(source.id || "unset")}</div>
          ${sourceInput(index, "id", source.id)}
        </div>
      </td>
      <td>${sourceInput(index, "enabled", String(Boolean(source.enabled)), "select")}</td>
      <td>${sourceInput(index, "source_organization", source.source_organization)}</td>
      <td>${sourceInput(index, "base_url", source.base_url)}</td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="seed_urls">${(source.seed_urls || []).join("\n")}</textarea>
      </td>
      <td>
        <div class="cell-stack">
          ${sourceInput(index, "type", source.type)}
          ${sourceInput(index, "discovery_mode", source.discovery_mode)}
        </div>
      </td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="geography_tags">${(source.geography_tags || []).join("\n")}</textarea>
      </td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="notes">${escapeHtml(source.notes || "")}</textarea>
      </td>
      <td>
        <div class="row-actions">
          <button class="button" data-remove-source="${index}">Remove</button>
        </div>
      </td>
    </tr>
  `;
}

function candidateRow(candidate) {
  return `
    <tr>
      <td class="cell-title">
        <div class="cell-stack">
          <strong>${escapeHtml(candidate.label)}</strong>
          <div class="cell-subtitle">${escapeHtml(candidate.notes || "")}</div>
        </div>
      </td>
      <td><span class="meta-pill">${escapeHtml(candidate.status)}</span></td>
      <td><span class="meta-pill">${escapeHtml(candidate.priority)}</span></td>
      <td><span class="meta-pill">${escapeHtml(candidate.source_type)}</span></td>
      <td>${escapeHtml(candidate.base_url)}</td>
      <td>${escapeHtml(candidate.seed_url || "")}</td>
      <td>
        <div class="tag-list">
          ${(candidate.geography_tags || []).map((tag) => `<span class="meta-pill">${escapeHtml(tag)}</span>`).join("")}
        </div>
      </td>
      <td>
        <div class="tag-list">
          <span class="meta-pill">${escapeHtml(candidate.parser_difficulty || "unknown")}</span>
          <span class="meta-pill">${escapeHtml(candidate.discovery_shape || "")}</span>
        </div>
      </td>
    </tr>
  `;
}
