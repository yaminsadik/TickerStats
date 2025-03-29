from flask import Blueprint, request, send_file, jsonify
import yfinance as yf
import pandas as pd
import io

export_bp = Blueprint('export', __name__)

@export_bp.route('/api/export')
def export_csv():
    tickers = request.args.get('ticker')
    if not tickers:
        return jsonify({"error": "Ticker is required"}), 400

    tickers = [t.strip().upper() for t in tickers.split(',')]
    records = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            record = {
                "Ticker": ticker,
                "Company": info.get("longName"),
                "Share Price": round(info.get("currentPrice", 0), 2),
                "Market Cap (B)": round(info.get("marketCap", 0) / 1e9, 2),
                "Enterprise Value (B)": round(info.get("enterpriseValue", 0) / 1e9, 2),
                "Forward P/E": round(info.get("forwardPE", 0), 2),
                "Price/Sales": round(info.get("priceToSalesTrailing12Months", 0), 2),
                "Price/Book": round(info.get("priceToBook", 0), 2),
                "EV/EBITDA": round(info.get("enterpriseToEbitda", 0), 2),
                "EV/Revenue": round(info.get("enterpriseToRevenue", 0), 2),
                "Profit Margin (%)": f"{round(info.get('profitMargins', 0) * 100, 2)}%",
                "ROA (%)": f"{round(info.get('returnOnAssets', 0) * 100, 2)}%",
                "ROE (%)": f"{round(info.get('returnOnEquity', 0) * 100, 2)}%",
                "Debt/Equity (%)": f"{round(info.get('debtToEquity', 0), 2)}%",
                "Beta": round(info.get("beta", 0), 2)
            }
            records.append(record)
        except Exception as e:
            continue

    df = pd.DataFrame(records)

    csv_stream = io.StringIO()
    df.to_csv(csv_stream, index=False)
    csv_stream.seek(0)

    return send_file(
        io.BytesIO(csv_stream.read().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='financial_summary.csv'
    )
