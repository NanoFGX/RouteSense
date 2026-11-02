import "leaflet/dist/leaflet.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { RiderApp } from "./RiderApp";
import { ReplyPage } from "./screens/ReplyPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/r/:token" element={<ReplyPage />} />
        <Route path="*" element={<RiderApp />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
