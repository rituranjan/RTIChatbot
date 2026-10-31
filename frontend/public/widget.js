(function () {
  var script = document.currentScript;
  if (!script) {
    var scripts = document.getElementsByTagName("script");
    for (var index = scripts.length - 1; index >= 0; index -= 1) {
      var candidate = scripts[index];
      if ((candidate.getAttribute("src") || "").indexOf("widget.js") !== -1 && candidate.getAttribute("data-bot")) {
        script = candidate;
        break;
      }
    }
  }
  if (!script) return;
  var bot = script.getAttribute("data-bot");
  if (!bot) return;
  var origin = script.src.replace(/\/widget\.js(?:\?.*)?$/, "");
  if (!origin) return;

  function mount() {
    if (!document.body || document.getElementById("chatbot-widget-frame")) return;
    var frame = document.createElement("iframe");
    frame.id = "chatbot-widget-frame";
    var site = "";
    try {
      site = window.location.origin || "";
    } catch (ignore) {}
    var siteQuery = site ? "&site=" + encodeURIComponent(site) : "";
    frame.src = origin + "/embed?bot=" + encodeURIComponent(bot) + siteQuery;
    frame.title = "Chat";
    frame.setAttribute("allowtransparency", "true");
    frame.setAttribute("allow", "clipboard-write");
    frame.style.cssText = [
      "position:fixed",
      "right:16px",
      "bottom:16px",
      "width:84px",
      "height:84px",
      "border:0",
      "z-index:2147483646",
      "background:transparent",
      "color-scheme:normal",
      "max-width:calc(100vw - 24px)",
      "max-height:calc(100vh - 24px)",
    ].join(";");
    window.addEventListener("message", function (event) {
      var data = event.data;
      if (!data || data.source !== "chatbot-widget" || event.source !== frame.contentWindow) return;
      if (data.open) {
        frame.style.width = "min(400px, calc(100vw - 24px))";
        frame.style.height = "min(700px, calc(100vh - 24px))";
      } else {
        frame.style.width = "84px";
        frame.style.height = "84px";
      }
    });
    document.body.appendChild(frame);
  }

  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
