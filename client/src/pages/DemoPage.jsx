import React, { useState } from "react";
import axios from "axios";
import "../App.css";
import { Navigation } from "../components/navigation";
import ThresholdToggle from "../components/threshold";

const DemoPage = () => {
  const [ticker, setTicker] = useState("");
  const [data, setData] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await axios.get(
        `https://tickerstats-22rs.onrender.com/api/metrics?ticker=${ticker}`
      );
      setData(res.data);
      setError("");
    } catch (err) {
      setError("Invalid ticker or server error.");
      setData([]);
    }
    setLoading(false);
  };

  const metrics = [
    { key: "share_price", label: "Share Price" },
    { key: "market_cap_billion", label: "Market Cap (B)" },
    { key: "enterprise_value_billion", label: "Enterprise Value (B)" },
    { key: "forward_pe", label: "Forward P/E" },
    { key: "price_sales", label: "Price/Sales" },
    { key: "price_book", label: "Price/Book" },
    { key: "ev_ebitda", label: "EV/EBITDA" },
    { key: "ev_revenue", label: "EV/Revenue" },
    { key: "profit_margin", label: "Profit Margin" },
    { key: "return_on_assets", label: "ROA" },
    { key: "return_on_equity", label: "ROE" },
    { key: "debt_equity", label: "Debt/Equity" },
    { key: "beta", label: "Beta" },
  ];

  const thresholds = {
    forward_pe: { value: 23.79, type: "lower" },
    price_sales: { value: 3.69, type: "lower" },
    price_book: { value: 8.91, type: "lower" },
    ev_ebitda: { value: 19.77, type: "lower" },
    ev_revenue: { value: 4.09, type: "lower" },
    profit_margin: { value: 0.133, type: "higher" },
    return_on_assets: { value: 0.0775, type: "higher" },
    return_on_equity: { value: 0.2588, type: "higher" },
    debt_equity: { value: 145.25, type: "lower" },
    beta: { value: 1.13, type: "lower" },
  };

  const isPercentageMetric = (key) =>
    ["profit_margin", "return_on_assets", "return_on_equity"].includes(key);

  const getCellColor = (key, value) => {
    if (!(key in thresholds) || typeof value !== "number") return "";
    const { value: threshold, type } = thresholds[key];
    if (type === "lower") {
      return value <= threshold ? "green-cell" : "red-cell";
    } else {
      return value >= threshold ? "green-cell" : "red-cell";
    }
  };

  const computeStats = (key, type) => {
    const values = data
      .map((d) => d[key])
      .filter((val) => typeof val === "number");

    if (values.length === 0) return "N/A";

    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance =
      values.reduce((sum, val) => sum + (val - mean) ** 2, 0) / values.length;
    const std = Math.sqrt(variance);

    let result;
    switch (type) {
      case "avg":
        result = mean;
        break;
      case "min":
        result = Math.min(...values);
        break;
      case "max":
        result = Math.max(...values);
        break;
      case "std":
        result = std;
        break;
      default:
        return "N/A";
    }
    return key === "debt_equity"
      ? result.toFixed(2) + "%"
      : isPercentageMetric(key)
      ? (result * 100).toFixed(2) + "%"
      : result.toFixed(2);
  };

  return (
    <>
      <Navigation />
      <div className="container" style={{ paddingTop: "100px" }}>
        <h1>📊 Bulldog Financials Comparison</h1>

        <div className="input-section">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="Enter tickers (e.g., AAPL, MSFT, TSLA)"
          />
          <button onClick={fetchMetrics}>Compare</button>
        </div>

        {loading && <p className="loading">Fetching data...</p>}
        {error && <p className="error">{error}</p>}

        {data.length > 0 && (
          <div className="table-container">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Company</th>
                  {metrics.map((m) => (
                    <th key={m.key}>{m.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((stock, idx) => (
                  <tr key={idx}>
                    <td>{stock.ticker}</td>
                    <td>{stock.company_name}</td>
                    {metrics.map((m) => (
                      <td
                        key={m.key}
                        className={getCellColor(m.key, stock[m.key])}
                      >
                        {typeof stock[m.key] === "number"
                          ? isPercentageMetric(m.key)
                            ? (stock[m.key] * 100).toFixed(2) + "%"
                            : m.key === "debt_equity"
                            ? stock[m.key].toFixed(2) + "%"
                            : stock[m.key].toFixed(2)
                          : "N/A"}
                      </td>
                    ))}
                  </tr>
                ))}

                {/* Summary Rows */}
                <tr>
                  <td>
                    <strong>Average</strong>
                  </td>
                  <td></td>
                  {metrics.map((m) => (
                    <td key={m.key}>{computeStats(m.key, "avg")}</td>
                  ))}
                </tr>
                <tr>
                  <td>
                    <strong>Minimum</strong>
                  </td>
                  <td></td>
                  {metrics.map((m) => (
                    <td key={m.key}>{computeStats(m.key, "min")}</td>
                  ))}
                </tr>
                <tr>
                  <td>
                    <strong>Maximum</strong>
                  </td>
                  <td></td>
                  {metrics.map((m) => (
                    <td key={m.key}>{computeStats(m.key, "max")}</td>
                  ))}
                </tr>
                <tr>
                  <td>
                    <strong>St. Dev</strong>
                  </td>
                  <td></td>
                  {metrics.map((m) => (
                    <td key={m.key}>{computeStats(m.key, "std")}</td>
                  ))}
                </tr>
              </tbody>
            </table>

            <div className="export-buttons">
              <button
                onClick={() => {
                  window.location.href = `https://tickerstats-22rs.onrender.com/api/export?ticker=${encodeURIComponent(ticker)}`;
                }}
              >
                📥 Export CSV
              </button>
              <button
                onClick={() => {
                  window.open(
                    `https://tickerstats-22rs.onrender.com/api/export-xlsx?ticker=${encodeURIComponent(ticker)}`
                  );
                }}
              >
                📥 Export Excel (with formatting)
              </button>
            </div>
            <ThresholdToggle />
          </div>
        )}
      </div>
    </>
  );
};

export default DemoPage;
