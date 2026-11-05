(function () {
  "use strict";

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.content : "";

  // ---------- Theme ----------
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("srms-theme", next);
      } catch (e) {}
    });
  });

  // ---------- Dropdowns and mobile nav ----------
  var openMenu = null;

  function closeMenu() {
    if (!openMenu) return;
    openMenu.panel.classList.remove("is-open");
    openMenu.button.setAttribute("aria-expanded", "false");
    openMenu = null;
  }

  document.querySelectorAll("[data-menu]").forEach(function (button) {
    var panel = document.getElementById(button.getAttribute("aria-controls"));
    if (!panel) return;
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      var wasOpen = openMenu && openMenu.panel === panel;
      closeMenu();
      if (wasOpen) return;
      panel.classList.add("is-open");
      button.setAttribute("aria-expanded", "true");
      openMenu = { button: button, panel: panel };
      if (panel.id === "notif-panel") loadNotificationPanel();
    });
  });

  document.addEventListener("click", function (event) {
    if (openMenu && !openMenu.panel.contains(event.target)) closeMenu();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && openMenu) {
      var button = openMenu.button;
      closeMenu();
      button.focus();
    }
  });

  var navToggle = document.querySelector("[data-nav-toggle]");
  var nav = document.getElementById("main-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // ---------- Notifications ----------
  var badge = document.getElementById("notif-count");
  var list = document.getElementById("notif-list");

  function setUnread(count) {
    if (!badge) return;
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count === 0;
    var bell = document.querySelector("[data-bell]");
    if (bell) bell.setAttribute("aria-label", "Notifications, " + count + " unread");
  }

  function timeAgo(iso) {
    var seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    var units = [["day", 86400], ["hour", 3600], ["minute", 60]];
    for (var i = 0; i < units.length; i++) {
      var n = Math.floor(seconds / units[i][1]);
      if (n >= 1) {
        if (units[i][0] === "day" && n > 30) break;
        return n + " " + units[i][0] + (n === 1 ? "" : "s") + " ago";
      }
    }
    return new Date(iso).toLocaleDateString();
  }

  function message(text) {
    var li = document.createElement("li");
    li.className = "panel-message";
    li.textContent = text;
    return li;
  }

  function renderPanel(data) {
    list.replaceChildren();
    if (!data.latest.length) {
      list.appendChild(message("You have no notifications yet."));
      return;
    }
    data.latest.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.className = "notif-link" + (item.unread ? "" : " is-read");
      a.href = item.url;
      var dot = document.createElement("span");
      dot.className = "unread-dot";
      dot.setAttribute("aria-hidden", "true");
      var body = document.createElement("span");
      var title = document.createElement("strong");
      title.textContent = item.title;
      var meta = document.createElement("small");
      meta.textContent = item.category + (item.important ? " · Important" : "") + " · " + timeAgo(item.created_at);
      if (item.unread) {
        var sr = document.createElement("span");
        sr.className = "sr-only";
        sr.textContent = "Unread: ";
        body.appendChild(sr);
      }
      body.appendChild(title);
      body.appendChild(meta);
      a.appendChild(dot);
      a.appendChild(body);
      li.appendChild(a);
      list.appendChild(li);
    });
  }

  function fetchSummary() {
    return fetch("/api/notifications/summary", { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        setUnread(data.unread);
        return data;
      });
  }

  function loadNotificationPanel() {
    if (!list) return;
    list.replaceChildren(message("Loading notifications…"));
    fetchSummary()
      .then(renderPanel)
      .catch(function () {
        list.replaceChildren(message("Could not load notifications. Check your connection and try again."));
      });
  }

  if (badge) {
    setInterval(function () {
      if (document.visibilityState === "visible") fetchSummary().catch(function () {});
    }, 30000);
  }

  // ---------- Flash messages ----------
  function dismiss(flash) {
    flash.classList.add("is-leaving");
    setTimeout(function () {
      flash.remove();
    }, 250);
  }

  document.querySelectorAll(".flash").forEach(function (flash) {
    var close = flash.querySelector("[data-dismiss]");
    if (close) close.addEventListener("click", function () { dismiss(flash); });
    if (!flash.classList.contains("flash-error")) {
      setTimeout(function () { if (document.body.contains(flash)) dismiss(flash); }, 7000);
    }
  });

  // ---------- Confirm dialog for destructive forms ----------
  var dialog = document.getElementById("confirm-dialog");
  var pendingForm = null;

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (form.dataset.confirmed === "yes" || !dialog || typeof dialog.showModal !== "function") return;
      event.preventDefault();
      pendingForm = form;
      dialog.querySelector("[data-confirm-title]").textContent = form.dataset.confirmTitle || "Are you sure?";
      dialog.querySelector("[data-confirm-text]").textContent = form.dataset.confirm;
      dialog.querySelector("[data-confirm-ok]").textContent = form.dataset.confirmOk || "Delete";
      dialog.returnValue = "";
      dialog.showModal();
    });
  });

  if (dialog) {
    dialog.addEventListener("close", function () {
      if (dialog.returnValue === "ok" && pendingForm) {
        pendingForm.dataset.confirmed = "yes";
        if (pendingForm.requestSubmit) pendingForm.requestSubmit();
        else pendingForm.submit();
      }
      pendingForm = null;
    });
  }

  // ---------- Loading state on submit ----------
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented || form.getAttribute("method") !== "post") return;
      var submitter = event.submitter;
      if (submitter && submitter.hasAttribute("data-no-loading")) return;
      var buttons = form.querySelectorAll('button[type="submit"]');
      var shown = submitter || buttons[0];
      if (!shown) return;
      setTimeout(function () {
        buttons.forEach(function (b) { b.disabled = true; });
        shown.classList.add("is-loading");
        var spinner = document.createElement("span");
        spinner.className = "spinner";
        spinner.setAttribute("aria-hidden", "true");
        shown.prepend(spinner);
      }, 0);
    });
  });

  // Pages restored from the back/forward cache must not keep a disabled button.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    document.querySelectorAll('form button[type="submit"]').forEach(function (button) {
      button.disabled = false;
      button.classList.remove("is-loading");
      var spinner = button.querySelector(".spinner");
      if (spinner) spinner.remove();
    });
  });

  // ---------- Password visibility ----------
  document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
    var input = document.getElementById(btn.getAttribute("aria-controls"));
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  // ---------- Demo account quick fill ----------
  document.querySelectorAll("[data-demo-user]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.getElementById("username").value = btn.dataset.demoUser;
      document.getElementById("password").value = btn.dataset.demoPass;
      document.getElementById("password").focus();
    });
  });

  // ---------- Live result preview (the server recalculates and validates on save) ----------
  var marksInput = document.getElementById("marks_obtained");
  var totalInput = document.getElementById("total_marks");
  var preview = document.getElementById("result-preview");
  if (marksInput && totalInput && preview) {
    var bands = [[90, "A+"], [80, "A"], [70, "B"], [60, "C"], [40, "D"]];
    var out = {
      pct: preview.querySelector("[data-preview-pct]"),
      grade: preview.querySelector("[data-preview-grade]"),
      status: preview.querySelector("[data-preview-status]"),
      note: document.getElementById("preview-note"),
    };
    var updatePreview = function () {
      var marks = Number(marksInput.value);
      var total = Number(totalInput.value);
      var problem = "";
      if (marksInput.value.trim() === "" || totalInput.value.trim() === "") problem = "Enter marks to see the grade.";
      else if (!isFinite(marks) || !isFinite(total)) problem = "Marks must be numbers.";
      else if (total <= 0) problem = "Total marks must be greater than 0.";
      else if (marks < 0) problem = "Marks cannot be negative.";
      else if (marks > total) problem = "Marks obtained cannot be more than total marks.";
      if (problem) {
        out.pct.textContent = "–";
        out.grade.textContent = "–";
        out.status.textContent = "–";
        out.note.textContent = problem;
        return;
      }
      var pct = Math.round((marks / total) * 10000 + 1e-9) / 100;
      var grade = "F";
      for (var i = 0; i < bands.length; i++) {
        if (pct >= bands[i][0]) { grade = bands[i][1]; break; }
      }
      out.pct.textContent = pct.toFixed(2) + "%";
      out.grade.textContent = grade;
      out.status.textContent = pct >= 40 ? "Pass" : "Fail";
      out.note.textContent = "Preview only. The result is recalculated and checked on the server when you save.";
    };
    marksInput.addEventListener("input", updatePreview);
    totalInput.addEventListener("input", updatePreview);
    updatePreview();
  }
})();

(function () {
  "use strict";
  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });
})();
