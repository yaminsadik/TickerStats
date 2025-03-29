from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

def get_metric(info, key, divisor=1, round_to=3):
    try:
        val = info.get(key, None)
        if val is None:
            return None
        return round(val / divisor, round_to)
    except:
        return None

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        data = {
            "ticker": ticker.upper(),
            "company_name": info.get("longName"),
            "share_price": get_metric(info, "currentPrice"),
            "market_cap_billion": get_metric(info, "marketCap", divisor=1e9),
            "enterprise_value_billion": get_metric(info, "enterpriseValue", divisor=1e9),
            "forward_pe": get_metric(info, "forwardPE"),
            "price_sales": get_metric(info, "priceToSalesTrailing12Months"),
            "price_book": get_metric(info, "priceToBook"),
            "ev_ebitda": get_metric(info, "enterpriseToEbitda"),
            "ev_revenue": get_metric(info, "enterpriseToRevenue"),
            "profit_margin": get_metric(info, "profitMargins"),
            "return_on_assets": get_metric(info, "returnOnAssets"),
            "return_on_equity": get_metric(info, "returnOnEquity"),
            "debt_equity": get_metric(info, "debtToEquity"),
            "beta": get_metric(info, "beta")
        }

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
