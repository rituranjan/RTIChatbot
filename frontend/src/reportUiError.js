import html2canvas from "html2canvas";

let reporting = false;
let lastKey = "";
let lastAt = 0;

export async function reportUiError(error, extra = {}) {
  const message = String(error?.message || error || "UI error").slice(0, 4000);
  const stack = String(error?.stack || "").slice(0, 20000);
  const path = String(extra.path || `${window.location.pathname}${window.location.search}`).slice(0, 500);
  if (!message && !stack) return;
  if (path.includes("/api/client-errors")) return;
  const key = `${path}|${message}`;
  const now = Date.now();
  if (reporting || (key === lastKey && now - lastAt < 10000)) return;
  reporting = true;
  lastKey = key;
  lastAt = now;
  try {
    const form = new FormData();
    form.append("message", message);
    form.append("stack", stack);
    form.append("path", path);
    try {
      const canvas = await html2canvas(document.body, {
        logging: false,
        scale: 0.4,
        useCORS: true,
        backgroundColor: "#ffffff",
      });
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (blob && blob.size > 0 && blob.size <= 2000000) {
        form.append("screenshot", blob, "ui.png");
      }
    } catch {
      // The failure is still stored when the page cannot be drawn.
    }
    await fetch("/api/client-errors/", { method: "POST", body: form, credentials: "include" });
  } catch {
    // Reporting must not create another visible failure.
  } finally {
    reporting = false;
  }
}
