// Progressive enhancement only - every page works without JS.
(function () {
  "use strict";

  // Mobile sidebar toggle
  var toggle = document.querySelector("[data-menu-toggle]");
  var sidebar = document.querySelector(".sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("is-open");
    });
    document.addEventListener("click", function (e) {
      if (
        window.innerWidth <= 860 &&
        sidebar.classList.contains("is-open") &&
        !sidebar.contains(e.target) &&
        e.target !== toggle
      ) {
        sidebar.classList.remove("is-open");
      }
    });
  }

  // Confirmation modals for destructive POST forms.
  // <form data-confirm="Message"> ... </form>
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (form.dataset.confirmed === "1") return;
      e.preventDefault();
      var dialog = document.getElementById("confirm-modal");
      if (!dialog || typeof dialog.showModal !== "function") {
        if (window.confirm(form.dataset.confirm)) {
          form.dataset.confirmed = "1";
          form.submit();
        }
        return;
      }
      dialog.querySelector("[data-confirm-message]").textContent = form.dataset.confirm;
      dialog.returnValue = "";
      dialog.showModal();
      dialog.addEventListener(
        "close",
        function () {
          if (dialog.returnValue === "confirm") {
            form.dataset.confirmed = "1";
            form.submit();
          }
        },
        { once: true }
      );
    });
  });

  // Auto-dismiss flash messages
  document.querySelectorAll(".messages li").forEach(function (li) {
    setTimeout(function () {
      li.style.transition = "opacity .4s";
      li.style.opacity = "0";
      setTimeout(function () { li.remove(); }, 400);
    }, 6000);
  });

  // Policy comparison picker: build ?ids= from checkboxes
  var compareForm = document.querySelector("[data-compare-form]");
  if (compareForm) {
    compareForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var ids = Array.prototype.slice
        .call(compareForm.querySelectorAll("input[name=compare]:checked"))
        .map(function (c) { return c.value; });
      if (ids.length < 2) {
        alert("Pick at least two policies to compare.");
        return;
      }
      window.location = compareForm.dataset.compareForm + "?ids=" + ids.join(",");
    });
  }
})();
