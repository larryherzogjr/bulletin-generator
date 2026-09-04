(function () {
  "use strict";

  document.querySelectorAll("form.confirm-delete").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm("Delete this week? This cannot be undone.")) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll(".protect-week-checkbox").forEach(function (checkbox) {
    checkbox.addEventListener("change", async function () {
      const protectedState = checkbox.checked;
      const row = checkbox.closest(".week-row");
      const deleteButton = row.querySelector(".confirm-delete button");
      checkbox.disabled = true;
      try {
        const response = await fetch(checkbox.dataset.protectUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ protected: protectedState })
        });
        if (!response.ok) throw new Error("Protection update failed");
        row.classList.toggle("is-protected", protectedState);
        deleteButton.disabled = protectedState;
        deleteButton.title = protectedState ? "Uncheck Keep before deleting" : "";
      } catch (_error) {
        checkbox.checked = !protectedState;
        window.alert("The protection setting could not be saved. Please try again.");
      } finally {
        checkbox.disabled = false;
      }
    });
  });
})();
