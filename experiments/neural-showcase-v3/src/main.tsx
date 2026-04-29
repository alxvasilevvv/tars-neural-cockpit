import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import "@/index.css";

// React Router v6 → v7 forward-compat opt-in. Silences the runtime
// future-flag warnings + lets us upgrade later without behavior drift.
//   - v7_startTransition: state updates wrapped in React.startTransition
//   - v7_relativeSplatPath: relative resolution within splat routes
const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={import.meta.env.BASE_URL} future={ROUTER_FUTURE}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
