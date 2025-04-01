import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import DemoPage from './pages/DemoPage';
import reportWebVitals from './reportWebVitals';

import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Router>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/demo" element={<DemoPage />} />
      </Routes>
    </Router>
  </React.StrictMode>
);

reportWebVitals();
