import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { reportUiError } from "./reportUiError";
import "./styles/main.css";

window.addEventListener("error", (event) => {
  reportUiError(event.error || event.message);
});
window.addEventListener("unhandledrejection", (event) => {
  reportUiError(event.reason);
});

class ErrorBoundary extends React.Component {
  componentDidCatch(error) {
    reportUiError(error);
  }

  render() {
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);