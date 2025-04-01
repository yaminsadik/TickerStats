import React from "react";

export const TryUs = () => {
  return (
    <section
      id="demo"
      className="text-center"
      style={{ padding: "80px 0", backgroundColor: "#f9f9f9" }}
    >
      <div className="container">
        <h2>🚀 Try TickerStats Now</h2>
        <p>Click below to test our live relative valuation engine.</p>

        <a href="/demo" className="btn btn-custom btn-lg" style={{ marginTop: "30px" }}>
          Try Now
        </a>
      </div>
    </section>
  );
};
