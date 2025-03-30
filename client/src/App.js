import React from "react";
import { Routes, Route } from "react-router-dom";
import LandingPage from "./components/LandingPage.jsx";
import Dashboard from "./components/Dashboard.jsx"; // <-- new file

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
    </Routes>
  );
}

export default App;
