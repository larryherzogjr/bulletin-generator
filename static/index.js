(function () {
  "use strict";

  document.querySelectorAll("form.confirm-delete").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm("Delete this week? This cannot be undone.")) {
        event.preventDefault();
      }
    });
  });
})();
