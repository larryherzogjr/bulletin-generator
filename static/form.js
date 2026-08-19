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
  let hymnLibraryPromise = null;
  const pendingHymnLoads = new Set();
  const scheduledHymnControls = new Set();
  let esvLookupPromise = null;
  let esvLookupTimer = null;
  let esvRequestVersion = 0;

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

  // ---- Ambassador hymn lookup -------------------------------------------
  // The global library stays outside each weekly JSON snapshot. Only the
  // three selected texts are copied into the existing large-print fields.
  function normalizedHymnNumber(value) {
    const raw = String(value || "").trim();
    if (!/^\d+$/.test(raw)) return null;
    const number = Number(raw);
    return Number.isInteger(number) && number >= 1 && number <= 634
      ? String(number)
      : null;
  }

  function loadHymnLibrary() {
    if (!hymnLibraryPromise) {
      hymnLibraryPromise = fetch(form.dataset.hymnLibraryUrl).then(async function (res) {
        if (!res.ok) throw new Error("hymn library failed to load (HTTP " + res.status + ")");
        const library = await res.json();
        if (!library || typeof library !== "object" || !library["1"] || !library["634"]) {
          throw new Error("hymn library is incomplete");
        }
        return library;
      });
      // Permit a deliberate retry from the Load lyrics button after a
      // temporary static-file/network failure.
      hymnLibraryPromise.catch(function () {
        hymnLibraryPromise = null;
      });
    }
    return hymnLibraryPromise;
  }

  function setHymnStatus(control, message, className) {
    control.status.textContent = message;
    control.status.className = "hymn-lookup-status" + (className ? " " + className : "");
  }

  function setHymnButton(control, label, disabled) {
    control.button.textContent = label;
    control.button.disabled = disabled;
  }

  function trackHymnLoad(promise) {
    pendingHymnLoads.add(promise);
    promise.then(
      function () { pendingHymnLoads.delete(promise); },
      function () { pendingHymnLoads.delete(promise); }
    );
    return promise;
  }

  function clearScheduledHymn(control) {
    if (control.lookupTimer !== null) {
      clearTimeout(control.lookupTimer);
      control.lookupTimer = null;
    }
    scheduledHymnControls.delete(control);
  }

  function runAutomaticHymnLookup(control) {
    clearScheduledHymn(control);
    const nextNumber = normalizedHymnNumber(control.input.value);
    const previousNumber = control.currentNumber;
    if (nextNumber) control.currentNumber = nextNumber;
    return trackHymnLoad(populateHymn(control, previousNumber, false));
  }

  function scheduleAutomaticHymnLookup(control) {
    clearScheduledHymn(control);
    scheduledHymnControls.add(control);
    control.lookupTimer = setTimeout(function () {
      runAutomaticHymnLookup(control);
    }, 300);
  }

  async function populateHymn(control, previousNumber, force) {
    const hymnNumber = normalizedHymnNumber(control.input.value);
    if (!hymnNumber) {
      const hasValue = String(control.input.value || "").trim();
      setHymnStatus(
        control,
        hasValue ? "Enter an Ambassador hymn number from 1 through 634." : "",
        hasValue ? "error" : ""
      );
      setHymnButton(control, "Load lyrics", true);
      return false;
    }

    const requestVersion = ++control.requestVersion;
    setHymnStatus(control, "Loading Ambassador hymn #" + hymnNumber + "…", "");
    setHymnButton(control, "Loading…", true);
    try {
      const library = await loadHymnLibrary();
      if (
        requestVersion !== control.requestVersion ||
        normalizedHymnNumber(control.input.value) !== hymnNumber
      ) {
        return false;
      }

      const newLyrics = library[hymnNumber];
      if (typeof newLyrics !== "string" || !newLyrics.trim()) {
        throw new Error("Ambassador hymn #" + hymnNumber + " is unavailable");
      }
      const currentLyrics = control.target.value.trim();
      const previousLyrics = previousNumber ? library[previousNumber] : null;
      const safeToReplace =
        force ||
        !currentLyrics ||
        (typeof previousLyrics === "string" && currentLyrics === previousLyrics);

      if (!safeToReplace) {
        setHymnStatus(
          control,
          "Existing edited lyrics were kept. Use Replace lyrics to load hymn #" + hymnNumber + ".",
          ""
        );
        setHymnButton(control, "Replace lyrics", false);
        return false;
      }

      if (control.target.value !== newLyrics) {
        control.target.value = newLyrics;
        // Programmatic value changes do not emit input events themselves. The
        // event makes the existing dirty/save workflow persist the new text.
        control.target.dispatchEvent(new Event("input", { bubbles: true }));
      }
      setHymnStatus(
        control,
        "Loaded all verses from Ambassador hymn #" + hymnNumber + ".",
        "loaded"
      );
      setHymnButton(control, "Reload lyrics", false);
      return true;
    } catch (err) {
      if (requestVersion === control.requestVersion) {
        setHymnStatus(
          control,
          "Lyrics could not be loaded; existing text was kept. " + err.message,
          "error"
        );
        setHymnButton(control, "Retry lyrics", false);
      }
      return false;
    }
  }

  const hymnControls = Array.from(form.querySelectorAll("[data-hymn-number]")).map(
    function (input) {
      const row = input.closest("[data-hymn-row]");
      const target = form.querySelector(
        '[data-key="' + cssEscape(input.dataset.hymnTarget) + '"]'
      );
      const control = {
        input: input,
        target: target,
        button: row.querySelector("[data-hymn-load]"),
        status: row.nextElementSibling,
        currentNumber: normalizedHymnNumber(input.value),
        requestVersion: 0,
        lookupTimer: null,
      };

      input.addEventListener("input", function () {
        const valid = normalizedHymnNumber(input.value);
        setHymnButton(control, "Load lyrics", !valid);
        if (valid) {
          scheduleAutomaticHymnLookup(control);
        } else {
          clearScheduledHymn(control);
          // Prevent an older in-flight lookup from populating after the number
          // has been cleared or made invalid.
          control.requestVersion += 1;
          const hasValue = String(input.value || "").trim();
          setHymnStatus(
            control,
            hasValue ? "Enter an Ambassador hymn number from 1 through 634." : "",
            hasValue ? "error" : ""
          );
        }
      });
      input.addEventListener("change", function () {
        if (control.lookupTimer !== null) runAutomaticHymnLookup(control);
      });
      control.button.addEventListener("click", function () {
        clearScheduledHymn(control);
        const nextNumber = normalizedHymnNumber(input.value);
        if (nextNumber) control.currentNumber = nextNumber;
        trackHymnLoad(populateHymn(control, null, true));
      });

      setHymnButton(control, "Load lyrics", !control.currentNumber);
      if (control.currentNumber && !target.value.trim()) {
        trackHymnLoad(populateHymn(control, control.currentNumber, false));
      }
      return control;
    }
  );

  // Warm the cache early so a normal number change is effectively immediate.
  loadHymnLibrary().catch(function () {
    hymnControls.forEach(function (control) {
      if (normalizedHymnNumber(control.input.value) && !control.status.textContent) {
        setHymnStatus(control, "Hymn library unavailable; use Load lyrics to retry.", "error");
      }
    });
  });

  // ---- official ESV Scripture lookup ------------------------------------
  // The browser sends references only. The server owns the API key, returns
  // temporary text for preview, and fetches the passages again for rendering.
  const esvSource = form.querySelector("#scripture-text-source");
  const esvButton = form.querySelector("#load-esv-scripture");
  const esvStatus = form.querySelector("#esv-lookup-status");
  const esvTextTargets = [
    form.querySelector('[data-key="weekly.large_print.call_to_worship_text"]'),
    form.querySelector('[data-key="weekly.memory_verse_text"]'),
    form.querySelector('[data-key="weekly.large_print.first_lesson_text"]'),
    form.querySelector('[data-key="weekly.large_print.second_lesson_text"]'),
  ];
  const esvLabelTargets = [
    form.querySelector('[data-key="weekly.large_print.first_lesson_label"]'),
    form.querySelector('[data-key="weekly.large_print.second_lesson_label"]'),
  ];

  function setEsvStatus(message, className) {
    esvStatus.textContent = message;
    esvStatus.className = "esv-lookup-status" + (className ? " " + className : "");
  }

  function scriptureReferences() {
    const lessonRows = Array.from(
      form.querySelectorAll('[data-list="weekly.scripture_lessons"] > .row')
    );
    return [
      form.querySelector('[data-key="weekly.call_to_worship"]').value.trim(),
      form.querySelector('[data-key="weekly.memory_verse_ref"]').value.trim(),
      lessonRows[0] ? lessonRows[0].querySelector('[data-col="0"]').value.trim() : "",
      lessonRows[1] ? lessonRows[1].querySelector('[data-col="0"]').value.trim() : "",
    ];
  }

  function syncEsvMode() {
    const automatic = esvSource.value === "esv";
    esvButton.disabled = false;
    esvTextTargets.concat(esvLabelTargets).forEach(function (target) {
      target.readOnly = automatic;
    });
    esvButton.textContent = automatic
      ? "Load / refresh ESV text"
      : "Use automatic ESV";
    if (!automatic) setEsvStatus("Manual Scripture text is stored with this week.", "");
  }

  async function loadEsvScripture() {
    if (esvSource.value !== "esv") return false;
    if (form.dataset.esvConfigured !== "true") {
      setEsvStatus("Automatic ESV is not configured on the server. Set ESV_API_KEY.", "error");
      return false;
    }
    const references = scriptureReferences();
    const missing = [
      "Call to Worship reference",
      "Memory Verse reference",
      "first lesson reference",
      "second lesson reference",
    ].filter(function (_label, index) { return !references[index]; });
    if (missing.length) {
      setEsvStatus("Add the " + missing.join(", ") + " before loading ESV text.", "error");
      return false;
    }

    const requestVersion = ++esvRequestVersion;
    const referenceSnapshot = JSON.stringify(references);
    esvButton.disabled = true;
    setEsvStatus("Loading official ESV text…", "");

    let lookup;
    lookup = (async function () {
      try {
        const response = await fetch(form.dataset.esvUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ references: references }),
        });
        let result;
        try {
          result = await response.json();
        } catch (_err) {
          result = { ok: false, error: "ESV lookup failed (HTTP " + response.status + ")" };
        }
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "ESV lookup failed");
        }
        if (
          requestVersion !== esvRequestVersion ||
          referenceSnapshot !== JSON.stringify(scriptureReferences()) ||
          esvSource.value !== "esv"
        ) {
          return false;
        }
        if (!Array.isArray(result.passages) || result.passages.length !== 4) {
          throw new Error("The ESV lookup returned an incomplete response.");
        }
        esvTextTargets.forEach(function (target, index) {
          target.value = result.passages[index].text;
        });
        esvLabelTargets[0].value = result.passages[2].heading;
        esvLabelTargets[1].value = result.passages[3].heading;
        setEsvStatus(
          "Loaded four official ESV passages. They will be refreshed when files are generated.",
          "loaded"
        );
        return true;
      } catch (err) {
        if (requestVersion === esvRequestVersion) {
          setEsvStatus("ESV text could not be loaded. " + err.message, "error");
        }
        return false;
      } finally {
        if (requestVersion === esvRequestVersion) esvButton.disabled = false;
      }
    })();
    esvLookupPromise = lookup;
    try {
      return await lookup;
    } finally {
      if (esvLookupPromise === lookup) esvLookupPromise = null;
    }
  }

  function scheduleEsvLookup() {
    if (esvSource.value !== "esv") return;
    if (esvLookupTimer !== null) clearTimeout(esvLookupTimer);
    esvLookupTimer = setTimeout(function () {
      esvLookupTimer = null;
      loadEsvScripture();
    }, 350);
  }

  esvButton.addEventListener("click", function () {
    if (esvSource.value !== "esv") {
      esvSource.value = "esv";
      esvSource.dispatchEvent(new Event("input", { bubbles: true }));
      syncEsvMode();
    }
    loadEsvScripture();
  });
  esvSource.addEventListener("change", function () {
    esvRequestVersion += 1;
    syncEsvMode();
    if (esvSource.value === "esv") loadEsvScripture();
  });
  form.addEventListener("change", function (event) {
    const target = event.target;
    if (
      target.matches('[data-key="weekly.call_to_worship"]') ||
      target.matches('[data-key="weekly.memory_verse_ref"]') ||
      (target.matches('[data-col="0"]') && target.closest('[data-list="weekly.scripture_lessons"]'))
    ) {
      scheduleEsvLookup();
    }
  });
  form.addEventListener("click", function (event) {
    if (
      event.target.matches('[data-target="weekly.scripture_lessons"]') ||
      (event.target.matches(".row-del") && event.target.closest('[data-list="weekly.scripture_lessons"]'))
    ) {
      scheduleEsvLookup();
    }
  });

  syncEsvMode();
  if (esvSource.value === "esv") loadEsvScripture();

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

    // optional sections: {enabled, text?, insert_text?} and
    // {enabled, grace, zion}
    form.querySelectorAll("[data-optional]").forEach(function (block) {
      const obj = { enabled: block.querySelector("[data-enable]").checked };
      const text = block.querySelector("[data-text]");
      if (text) obj.text = text.value;
      block.querySelectorAll("[data-option-field]").forEach(function (el) {
        obj[el.dataset.optionField] = el.value;
      });
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

  async function waitForAutomaticLookups() {
    // A save can occur during the short typing debounce. Flush those lookups
    // first so references and their selected source are saved atomically.
    Array.from(scheduledHymnControls).forEach(runAutomaticHymnLookup);
    if (esvLookupTimer !== null) {
      clearTimeout(esvLookupTimer);
      esvLookupTimer = null;
      loadEsvScripture();
    }
    while (pendingHymnLoads.size || esvLookupPromise) {
      const lookups = Array.from(pendingHymnLoads);
      if (esvLookupPromise) lookups.push(esvLookupPromise);
      await Promise.all(lookups);
    }
  }

  async function saveAfterAutomaticLookups() {
    if (
      pendingHymnLoads.size || scheduledHymnControls.size ||
      esvLookupPromise || esvLookupTimer !== null
    ) {
      statusEl.textContent = "Finishing automatic lookups…";
      statusEl.className = "saving";
      saveBtn.disabled = true;
      generateLink.setAttribute("aria-busy", "true");
    }
    await waitForAutomaticLookups();
    return performSave(revision);
  }

  async function save() {
    if (savePromise) return savePromise;
    savePromise = saveAfterAutomaticLookups();
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
