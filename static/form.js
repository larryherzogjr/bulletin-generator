/* Bulletin form (M3): add/remove repeatable rows and serialize the whole
 * form back into the canonical {weekly, standing, insert} blob, then POST it.
 *
 * The DOM is the source of truth. data-* attributes describe where each input
 * belongs in the blob:
 *   data-key="weekly.date"            -> scalar string at that path
 *   data-obj + data-objkey            -> hymn sub-dict {grace,title,zion}
 *   data-list + rows with data-col    -> list of pairs/singles
 *   data-events + event-day blocks    -> [[day, [[name,time],...]], ...]
 *   data-anns + ann-row blocks        -> [{heading, body}, ...]
 */
(function () {
  "use strict";

  const form = document.getElementById("week-form");
  const statusEl = document.getElementById("save-status");
  const titleEl = document.getElementById("page-title");

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
    statusEl.textContent = "Unsaved changes";
    statusEl.className = "dirty";
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
    }
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

    // hymn objects
    form.querySelectorAll("[data-obj]").forEach(function (row) {
      const obj = {};
      row.querySelectorAll("[data-objkey]").forEach(function (inp) {
        obj[inp.dataset.objkey] = inp.value;
      });
      setPath(blob, row.dataset.obj, obj);
    });

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

    return blob;
  }

  // ---- save --------------------------------------------------------------
  const saveBtn = document.getElementById("save-btn");

  async function save() {
    statusEl.textContent = "Saving…";
    statusEl.className = "saving";
    try {
      const res = await fetch(form.dataset.saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serialize()),
      });
      const out = await res.json();
      if (out.ok) {
        statusEl.textContent = "Saved";
        statusEl.className = "saved";
        if (out.label) titleEl.textContent = out.label;
      } else {
        statusEl.textContent = "Error: " + (out.error || "save failed");
        statusEl.className = "dirty";
      }
    } catch (err) {
      statusEl.textContent = "Error: " + err.message;
      statusEl.className = "dirty";
    }
  }

  saveBtn.addEventListener("click", save);

  // Ctrl/Cmd-S saves
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      save();
    }
  });

  // Warn before leaving with unsaved edits
  window.addEventListener("beforeunload", function (e) {
    if (statusEl.className === "dirty") {
      e.preventDefault();
      e.returnValue = "";
    }
  });
})();
