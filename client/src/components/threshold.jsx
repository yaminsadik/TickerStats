import React, { useState } from "react";
import "../ThresholdLegend.css";

const thresholds = [
  { label: "Forward P/E", value: 23.79, direction: "≤ is green, > is red" },
  { label: "Price/Sales", value: 3.69, direction: "≤ is green, > is red" },
  { label: "Price/Book", value: 8.91, direction: "≤ is green, > is red" },
  { label: "EV/EBITDA", value: 19.77, direction: "≤ is green, > is red" },
  { label: "EV/Revenue", value: 4.09, direction: "≤ is green, > is red" },
  { label: "Profit Margin (%)", value: 13.3, direction: ">= is green, < is red" },
  { label: "ROA (%)", value: 7.75, direction: ">= is green, < is red" },
  { label: "ROE (%)", value: 25.88, direction: ">= is green, < is red" },
  { label: "Debt/Equity (%)", value: 145.25, direction: "≤ is green, > is red" },
  { label: "Beta", value: 1.13, direction: "≤ is green, > is red" },
];

function ThresholdToggle() {
  const [show, setShow] = useState(false);

  return (
    <div className="threshold-toggle-container">
      <button className="toggle-btn" onClick={() => setShow(!show)}>
        {show ? "Hide Thresholds" : "Show Thresholds"}
      </button>

      {show && (
        <div className="threshold-legend">
          <h2>📊 Conditional Formatting Thresholds</h2>
          <p className="description">
            Metrics are color-coded based on industry standards:
            <span className="green"> green</span> (favorable) and
            <span className="red"> red</span> (caution).
          </p>
          <table className="threshold-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Threshold</th>
                <th>Color Rule</th>
              </tr>
            </thead>
            <tbody>
              {thresholds.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.label}</td>
                  <td>{item.value}</td>
                  <td>{item.direction}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ThresholdToggle;