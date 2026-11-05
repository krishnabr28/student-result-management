// Loaded in <head> so the saved theme applies before the first paint.
(function () {
  var saved = null;
  try {
    saved = localStorage.getItem("srms-theme");
  } catch (e) {}
  var theme = saved === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
})();
