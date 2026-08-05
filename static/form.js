/* Bulletin form (M3): add/remove repeatable rows and serialize the whole
 * form back into the canonical {weekly, standing, insert} blob, then POST it.
 *
 * The DOM is the source of truth. data-* attributes describe where each input
 * belongs in the blob:
 *   data-key="weekly.date"            -> scalar string at that path
 *   data-list + rows with data-col    -> list of pairs/singles
 *   data-events + event-day blocks    -> [[day, [[name,time],...]], ...]
 *   data-anns + ann-row blocks        -> [{heading, body}, ...]
 */
(function () {
  "use strict";

  const form = document.getElementById("week-form");
  const statusEl = document.getElementById("save-status");
  const titleEl = document.getElementById("page-title");
  const saveBtn = document.getElementById("save-btn");
  const generateLink = document.getElementById("go-generate");
  let revision = 0;
  let savedRevision = 0;
  let savePromise = null;

  // ---- helpers ----------------------------------------------------------
  function setPath(obj, path, value) {
    const parts = path.split(".");
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      if (typeof cur[parts[i]] !== "object" || cur[parts[i]] === null) {
        cur[parts[i]] = {};
      }
      cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
  }

  function markDirty() {
    revision += 1;
    statusEl.textContent = "Unsaved changes";
    statusEl.className = "dirty";
  }

  function isDirty() {
    return revision !== savedRevision;
  }

  form.addEventListener("input", markDirty);

  // ---- optional sections: reflect enabled state visually -----------------
  function syncOptional(block) {
    block.classList.toggle("on", block.querySelector("[data-enable]").checked);
  }
  form.querySelectorAll("[data-optional]").forEach(syncOptional);
  form.addEventListener("change", function (e) {
    if (e.target.matches("[data-enable]")) {
      syncOptional(e.target.closest("[data-optional]"));
    }
  });

  // ---- add / remove rows -------------------------------------------------
  function cloneTpl(id) {
    return document.getElementById(id).content.firstElementChild.cloneNode(true);
  }

  // Every repeatable collection can be reordered. Nested event rows may move
  // between dates in the same parish; prayer names may move between categories.
  // Other collections remain inside their own semantic list.
  function orderConfig(container) {
    if (container.matches("[data-list]")) {
      return { item: ".row", group: "list:" + container.dataset.list, label: "row" };
    }
    if (container.matches("[data-events]")) {
      return { item: ".event-day", group: "days:" + container.dataset.events, label: "date" };
    }
    if (container.classList.contains("day-items")) {
      const events = container.closest("[data-events]");
      return { item: ".row", group: "event-items:" + events.dataset.events, label: "event" };
    }
    if (container.matches("[data-anns]")) {
      return { item: ".ann-row", group: "announcements", label: "announcement" };
    }
    if (container.matches("[data-prayer]")) {
      return { item: ".prayer-cat", group: "prayer-categories", label: "prayer category" };
    }
    if (container.classList.contains("cat-names")) {
      return { item: ".row", group: "prayer-names", label: "prayer name" };
    }
    return null;
  }

  function directItems(container) {
    const config = orderConfig(container);
    if (!config) return [];
    return Array.from(container.children).filter(function (child) {
      return child.matches(config.item);
    });
  }

  function addDragHandle(item, label) {
    if (item.querySelector(":scope > .drag-handle, :scope > .row > .drag-handle")) return;

    const handle = document.createElement("span");
    handle.className = "drag-handle";
    handle.setAttribute("role", "button");
    handle.setAttribute("tabindex", "0");
    handle.setAttribute("aria-label", "Reorder " + label);
    handle.title = "Drag to reorder; use arrow keys when focused";
    handle.textContent = "↕";

    const heading = item.querySelector(":scope > .day-head, :scope > .cat-head");
    (heading || item).insertBefore(handle, (heading || item).firstChild);
    item.classList.add("orderable-item");
  }

  function refreshOrderables() {
    form.querySelectorAll(
      "[data-list], [data-events], .day-items, [data-anns], [data-prayer], .cat-names"
    ).forEach(function (container) {
      const config = orderConfig(container);
      if (!config) return;
      container.classList.add("orderable-list");
      container.dataset.orderGroup = config.group;
      directItems(container).forEach(function (item) {
        addDragHandle(item, config.label);
      });
    });
  }

  let draggedItem = null;
  let sourceContainer = null;
  let sourceIndex = -1;
  let activeDropContainer = null;
  let dragHandle = null;
  let dragPointerId = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStarted = false;

  function directItemAt(container, target) {
    return directItems(container).find(function (item) {
      return item === target || item.contains(target);
    }) || null;
  }

  function clearDragState() {
    if (draggedItem) draggedItem.classList.remove("dragging");
    form.querySelectorAll(".orderable-list.drag-over").forEach(function (container) {
      container.classList.remove("drag-over");
    });
    draggedItem = null;
    sourceContainer = null;
    sourceIndex = -1;
    activeDropContainer = null;
    dragHandle = null;
    dragPointerId = null;
    dragStarted = false;
    document.body.classList.remove("reordering");
  }

  form.addEventListener("pointerdown", function (e) {
    const handle = e.target.closest(".drag-handle");
    if (!handle || e.button !== 0) return;
    e.preventDefault();
    handle.focus();
    dragHandle = handle;
    dragPointerId = e.pointerId;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    draggedItem = handle.closest(".orderable-item");
    sourceContainer = draggedItem.parentElement;
    sourceIndex = directItems(sourceContainer).indexOf(draggedItem);
    handle.setPointerCapture(e.pointerId);
  });

  form.addEventListener("pointermove", function (e) {
    if (!draggedItem || e.pointerId !== dragPointerId) return;
    if (!dragStarted) {
      const distance = Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY);
      if (distance < 4) return;
      dragStarted = true;
      draggedItem.classList.add("dragging");
      document.body.classList.add("reordering");
    }
    e.preventDefault();

    // Keep long lists usable: dragging near a viewport edge scrolls the page
    // while pointer capture keeps the item attached to the handle.
    const scrollEdge = 80;
    if (e.clientY < scrollEdge) {
      window.scrollBy(0, -Math.min(18, scrollEdge - e.clientY));
    } else if (e.clientY > window.innerHeight - scrollEdge) {
      window.scrollBy(0, Math.min(18, e.clientY - (window.innerHeight - scrollEdge)));
    }

    const pointed = document.elementFromPoint(e.clientX, e.clientY);
    const container = pointed ? pointed.closest(".orderable-list") : null;
    if (!container || container.dataset.orderGroup !== sourceContainer.dataset.orderGroup) return;

    if (activeDropContainer !== container) {
      if (activeDropContainer) activeDropContainer.classList.remove("drag-over");
      activeDropContainer = container;
      activeDropContainer.classList.add("drag-over");
    }

    const targetItem = directItemAt(container, pointed);
    if (!targetItem || targetItem === draggedItem) {
      if (!targetItem && container.lastElementChild !== draggedItem) {
        container.appendChild(draggedItem);
      }
      return;
    }

    const targetRect = targetItem.getBoundingClientRect();
    const after = e.clientY > targetRect.top + targetRect.height / 2;
    const reference = after ? targetItem.nextElementSibling : targetItem;
    if (reference !== draggedItem) container.insertBefore(draggedItem, reference);
  });

  function finishPointerDrag(e) {
    if (!draggedItem || e.pointerId !== dragPointerId) return;
    const finalContainer = draggedItem.parentElement;
    const finalIndex = directItems(finalContainer).indexOf(draggedItem);
    if (dragStarted && (finalContainer !== sourceContainer || finalIndex !== sourceIndex)) {
      markDirty();
    }
    if (dragHandle.hasPointerCapture(e.pointerId)) dragHandle.releasePointerCapture(e.pointerId);
    clearDragState();
  }

  form.addEventListener("pointerup", finishPointerDrag);
  form.addEventListener("pointercancel", finishPointerDrag);

  form.addEventListener("keydown", function (e) {
    const handle = e.target.closest(".drag-handle");
    if (!handle || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    const item = handle.closest(".orderable-item");
    const container = item.parentElement;
    const items = directItems(container);
    const index = items.indexOf(item);
    if (e.key === "ArrowUp" && index > 0) {
      container.insertBefore(item, items[index - 1]);
    } else if (e.key === "ArrowDown" && index < items.length - 1) {
      container.insertBefore(item, items[index + 1].nextElementSibling);
    } else {
      return;
    }
    e.preventDefault();
    markDirty();
    handle.focus();
  });

  refreshOrderables();

  form.addEventListener("click", function (e) {
    const t = e.target;

    if (t.classList.contains("add-row")) {
      const container = form.querySelector(
        '[data-list="' + cssEscape(t.dataset.target) + '"]'
      );
      const single = container.classList.contains("single");
      container.appendChild(cloneTpl(single ? "tpl-single" : "tpl-pair"));
      markDirty();
    } else if (t.classList.contains("row-del")) {
      t.closest(".row").remove();
      markDirty();
    } else if (t.classList.contains("add-day")) {
      const block = cloneTpl("tpl-event-day");
      t.previousElementSibling.appendChild(block); // the .events container
      markDirty();
    } else if (t.classList.contains("day-del")) {
      t.closest(".event-day").remove();
      markDirty();
    } else if (t.classList.contains("add-item")) {
      const items = t.previousElementSibling; // .day-items
      items.appendChild(cloneTpl("tpl-pair"));
      markDirty();
    } else if (t.classList.contains("add-ann")) {
      form.querySelector('[data-anns]').appendChild(cloneTpl("tpl-ann"));
      markDirty();
    } else if (t.classList.contains("ann-del")) {
      t.closest(".ann-row").remove();
      markDirty();
    } else if (t.classList.contains("add-cat")) {
      form.querySelector("[data-prayer]").appendChild(cloneTpl("tpl-prayer-cat"));
      markDirty();
    } else if (t.classList.contains("cat-del")) {
      t.closest(".prayer-cat").remove();
      markDirty();
    } else if (t.classList.contains("add-name")) {
      const names = t.previousElementSibling; // .cat-names
      names.appendChild(cloneTpl("tpl-single"));
      markDirty();
    }
    refreshOrderables();
  });

  // CSS.escape isn't universal for attr selectors here; dots are fine in
  // attribute *values*, so we only need to quote — provide a tiny fallback.
  function cssEscape(s) {
    return s.replace(/"/g, '\\"');
  }

  // ---- serialize ---------------------------------------------------------
  function serialize() {
    const blob = { weekly: {}, standing: {}, insert: {} };

    // scalars
    form.querySelectorAll("[data-key]").forEach(function (el) {
      setPath(blob, el.dataset.key, el.value);
    });

    // confession of faith radio
    const creed = form.querySelector('input[name="confession_of_faith"]:checked');
    setPath(blob, "weekly.confession_of_faith", creed ? creed.value : "");

    // optional sections: {enabled, text?} and {enabled, grace, zion}
    form.querySelectorAll("[data-optional]").forEach(function (block) {
      const obj = { enabled: block.querySelector("[data-enable]").checked };
      const text = block.querySelector("[data-text]");
      if (text) obj.text = text.value;
      block.querySelectorAll("[data-flag]").forEach(function (cb) {
        obj[cb.dataset.flag] = cb.checked;
      });
      setPath(blob, block.dataset.optional, obj);
    });

    // flat lists (pairs or singles)
    form.querySelectorAll("[data-list]").forEach(function (container) {
      const single = container.classList.contains("single");
      const rows = [];
      container.querySelectorAll(":scope > .row").forEach(function (row) {
        if (single) {
          rows.push(row.querySelector('[data-col="0"]').value);
        } else {
          rows.push([
            row.querySelector('[data-col="0"]').value,
            row.querySelector('[data-col="1"]').value,
          ]);
        }
      });
      setPath(blob, container.dataset.list, rows);
    });

    // events: [[day, [[name, time], ...]], ...]
    form.querySelectorAll("[data-events]").forEach(function (container) {
      const days = [];
      container.querySelectorAll(":scope > .event-day").forEach(function (block) {
        const day = block.querySelector("[data-day]").value;
        const items = [];
        block.querySelectorAll(".day-items > .row").forEach(function (row) {
          items.push([
            row.querySelector('[data-col="0"]').value,
            row.querySelector('[data-col="1"]').value,
          ]);
        });
        days.push([day, items]);
      });
      setPath(blob, container.dataset.events, days);
    });

    // announcements: [{heading, body}, ...]
    form.querySelectorAll("[data-anns]").forEach(function (container) {
      const anns = [];
      container.querySelectorAll(":scope > .ann-row").forEach(function (row) {
        anns.push({
          heading: row.querySelector('[data-annkey="heading"]').value,
          body: row.querySelector('[data-annkey="body"]').value,
        });
      });
      setPath(blob, container.dataset.anns, anns);
    });

    // prayer: [{label, names: [str]}, ...]
    form.querySelectorAll("[data-prayer]").forEach(function (container) {
      const cats = [];
      container.querySelectorAll(":scope > .prayer-cat").forEach(function (block) {
        const names = [];
        block.querySelectorAll(".cat-names > .row").forEach(function (row) {
          names.push(row.querySelector('[data-col="0"]').value);
        });
        cats.push({ label: block.querySelector("[data-cat-label]").value, names: names });
      });
      setPath(blob, container.dataset.prayer, cats);
    });

    return blob;
  }

  // ---- save --------------------------------------------------------------
  async function performSave(snapshotRevision) {
    statusEl.textContent = "Saving…";
    statusEl.className = "saving";
    saveBtn.disabled = true;
    generateLink.setAttribute("aria-busy", "true");
    try {
      const res = await fetch(form.dataset.saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serialize()),
      });
      let out;
      try {
        out = await res.json();
      } catch (_err) {
        out = { ok: false, error: "save failed (HTTP " + res.status + ")" };
      }
      if (res.ok && out.ok) {
        savedRevision = snapshotRevision;
        if (isDirty()) {
          statusEl.textContent = "Unsaved changes";
          statusEl.className = "dirty";
        } else {
          statusEl.textContent = "Saved";
          statusEl.className = "saved";
        }
        if (out.label) titleEl.textContent = out.label;
        return true;
      } else {
        statusEl.textContent = "Error: " + (out.error || "save failed");
        statusEl.className = "dirty";
        return false;
      }
    } catch (err) {
      statusEl.textContent = "Error: " + err.message;
      statusEl.className = "dirty";
      return false;
    } finally {
      saveBtn.disabled = false;
      generateLink.removeAttribute("aria-busy");
    }
  }

  async function save() {
    if (savePromise) return savePromise;
    const snapshotRevision = revision;
    savePromise = performSave(snapshotRevision);
    try {
      return await savePromise;
    } finally {
      savePromise = null;
    }
  }

  saveBtn.addEventListener("click", save);

  // Never navigate to generation while a save is pending or content is dirty.
  generateLink.addEventListener("click", async function (e) {
    if (!isDirty() && !savePromise) return;
    e.preventDefault();
    const destination = generateLink.href;
    do {
      if (!(await save())) return;
    } while (isDirty());
    window.location.assign(destination);
  });

  // Ctrl/Cmd-S saves
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      save();
    }
  });

  // Warn before leaving with unsaved edits
  window.addEventListener("beforeunload", function (e) {
    if (isDirty() || savePromise) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
})();
