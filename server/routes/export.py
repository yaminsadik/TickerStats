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
                "Share Price": info.get("currentPrice"),
                "Market Cap (B)": info.get("marketCap", 0) / 1e9,
                "Enterprise Value (B)": info.get("enterpriseValue", 0) / 1e9,
                "Forward P/E": info.get("forwardPE"),
                "Price/Sales": info.get("priceToSalesTrailing12Months"),
                "Price/Book": info.get("priceToBook"),
                "EV/EBITDA": info.get("enterpriseToEbitda"),
                "EV/Revenue": info.get("enterpriseToRevenue"),
                "Profit Margin (%)": info.get("profitMargins") * 100 if info.get("profitMargins") else None,
                "ROA (%)": info.get("returnOnAssets") * 100 if info.get("returnOnAssets") else None,
                "ROE (%)": info.get("returnOnEquity") * 100 if info.get("returnOnEquity") else None,
                "Debt/Equity (%)": info.get("debtToEquity"),
                "Beta": info.get("beta")
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
