import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const fetchMetrics = async () => {
    try {
      const res = await axios.get(`http://localhost:5000/api/metrics?ticker=${ticker}`);
      setData(res.data);
      setError('');
    } catch (err) {
      setError('Invalid ticker or server error.');
      setData(null);
    }
  };

  return (
    <div className="container">
      <h1>📊 Bulldog Financials Dashboard</h1>

      <div className="input-section">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Enter Ticker (e.g., AAPL)"
        />
        <button onClick={fetchMetrics}>Fetch Data</button>
      </div>

      {error && <p className="error">{error}</p>}

      {data && (
        <div className="table-container">
          <h2>{data.company_name} ({data.ticker})</h2>
          <table>
            <tbody>
              <TableRow label="Share Price" value={data.share_price} />
              <TableRow label="Market Cap (B)" value={data.market_cap_billion} />
              <TableRow label="Enterprise Value (B)" value={data.enterprise_value_billion} />
              <TableRow label="Forward P/E" value={data.forward_pe} />
              <TableRow label="Price/Sales" value={data.price_sales} />
              <TableRow label="Price/Book" value={data.price_book} />
              <TableRow label="EV/EBITDA" value={data.ev_ebitda} />
              <TableRow label="EV/Revenue" value={data.ev_revenue} />
              <TableRow label="Profit Margin" value={data.profit_margin} />
              <TableRow label="Return on Assets" value={data.return_on_assets} />
              <TableRow label="Return on Equity" value={data.return_on_equity} />
              <TableRow label="Debt/Equity" value={data.debt_equity} />
              <TableRow label="Beta" value={data.beta} />
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TableRow({ label, value }) {
  return (
    <tr>
      <td><strong>{label}</strong></td>
      <td>{value !== null ? value : 'N/A'}</td>
    </tr>
  );
}

export default App;
