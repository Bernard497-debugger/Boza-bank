import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 🛡️ LIVE CREDENTIALS
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
ENV = os.environ.get('PAYPAL_ENV', 'live') 
PAYPAL_BASE_URL = 'https://api-m.paypal.com' if ENV == 'live' else 'https://api-m.sandbox.paypal.com'

def get_access_token():
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return response.json().get('access_token')
    except Exception:
        return None

def get_app_data():
    token = get_access_token()
    if not token: return "0.00", [], 0.0
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    balance = "0.00"
    total_revenue = 0.0
    history = []
    
    try:
        b_res = requests.get(f"{PAYPAL_BASE_URL}/v1/reporting/balances?currency_code=USD", headers=headers, timeout=10)
        balance = b_res.json()['balances'][0]['total_balance']['value']
        
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        t_res = requests.get(
            f"{PAYPAL_BASE_URL}/v1/reporting/transactions?start_date={start_date}&end_date={datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}&fields=transaction_info", 
            headers=headers, timeout=10
        )
        for tx in t_res.json().get('transaction_details', []):
            info = tx.get('transaction_info', {})
            val = float(info.get('transaction_amount', {}).get('value', 0))
            if val > 0:
                total_revenue += val
                history.append({
                    "type": "Incoming",
                    "amount": val,
                    "date": info.get('transaction_initiation_date', '')[:10]
                })
    except: pass
    return balance, history, total_revenue

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | Payment Portal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD&components=buttons,card-fields"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; --glass: rgba(255, 255, 255, 0.03); }
        body { margin: 0; background: var(--bg); font-family: 'Inter', sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .app-container { width: 92%; max-width: 420px; padding: 30px; border-radius: 40px; background: var(--glass); backdrop-filter: blur(50px); border: 1px solid rgba(255, 255, 255, 0.1); position: relative; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
        .logo { font-weight: 900; font-size: 20px; color: var(--accent); }
        .share-btn { background: var(--glass); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 8px 15px; border-radius: 12px; font-size: 12px; cursor: pointer; }
        .balance-card { text-align: center; margin-bottom: 30px; }
        .balance-amount { font-size: 3.5rem; font-weight: 800; margin: 0; }
        .revenue-badge { display: inline-block; padding: 4px 12px; background: rgba(0, 255, 136, 0.1); color: #00ff88; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 8px; }
        .tabs { display: flex; gap: 5px; background: rgba(255,255,255,0.05); padding: 5px; border-radius: 20px; margin-bottom: 25px; }
        .tab-btn { flex: 1; padding: 12px; border-radius: 16px; border: none; background: transparent; color: white; opacity: 0.5; cursor: pointer; font-size: 13px; font-weight: 600; }
        .tab-btn.active { background: rgba(255,255,255,0.1); opacity: 1; }
        .amount-input { width: 100%; background: transparent; border: none; color: white; font-size: 2.8rem; font-weight: 800; text-align: center; margin-bottom: 10px; outline: none; }
        .btn-desc { font-size: 11px; opacity: 0.4; text-align: center; margin-top: 8px; display: block; line-height: 1.4; }
        .card-field { height: 55px; padding: 15px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; margin-bottom: 10px; box-sizing: border-box; }
        .action-sec { display: none; }
        .action-sec.active { display: block; }
        .submit-btn { width: 100%; padding: 20px; border-radius: 18px; border: none; background: white; color: black; font-weight: 800; cursor: pointer; font-size: 16px; margin-top: 10px; }
        .history { margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 20px; }
        .history-item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-size: 14px; }
        #success-overlay { display: none; position: absolute; inset: 0; background: #000; border-radius: 40px; z-index: 100; flex-direction: column; justify-content: center; align-items: center; padding: 20px; }
        .check { width: 70px; height: 70px; background: #00ff88; color: black; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 35px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="app-container">
        <div id="success-overlay">
            <div class="check">✓</div>
            <h2 style="margin: 0;">Payment Success</h2>
            <p style="opacity: 0.5; font-size: 14px;">The transaction has been captured and logged successfully.</p>
            <button class="submit-btn" onclick="location.reload()">Back to Dashboard</button>
        </div>
        <div class="header">
            <div class="logo">AuraPay</div>
            <button class="share-btn" onclick="copyLink()">Copy Link</button>
        </div>
        <div class="balance-card">
            <div style="opacity: 0.4; font-size: 10px; letter-spacing: 1px;">CURRENT ACCOUNT BALANCE</div>
            <div class="balance-amount">${{ balance }}</div>
            <div class="revenue-badge">Total Revenue: ${{ "%.2f"|format(total_revenue) }}</div>
        </div>
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('dep', this)">Deposit Funds</button>
            <button class="tab-btn" onclick="switchTab('rec', this)">Receive Payments</button>
        </div>
        <div style="text-align: center; opacity: 0.3; font-size: 11px;">Set Transaction Amount</div>
        <input type="number" id="main-amt" class="amount-input" value="10.00" step="0.01">
        <div id="dep-sec" class="action-sec active">
            <div id="paypal-button-container"></div>
            <span class="btn-desc">Use this to add funds yourself using your linked <br> PayPal account or debit card.</span>
        </div>
        <div id="rec-sec" class="action-sec">
            <div id="card-number-field" class="card-field"></div>
            <div style="display: flex; gap: 10px;">
                <div id="card-expiry-field" class="card-field" style="flex: 2;"></div>
                <div id="card-cvv-field" class="card-field" style="flex: 1;"></div>
            </div>
            <button id="card-btn" class="submit-btn">Complete Payment</button>
            <span class="btn-desc">Securely process payments from others. <br> Card details are handled via PayPal.</span>
        </div>
        <div class="history">
            <div style="font-size: 10px; opacity: 0.3; margin-bottom: 15px; letter-spacing: 1px;">TRANSACTION LOGS</div>
            {% for item in history[:4] %}
            <div class="history-item">
                <span>{{ item.type }}<br><small style="opacity:0.4">{{ item.date }}</small></span>
                <span style="font-weight: 800; color: #00ff88;">+${{ "%.2f"|format(item.amount) }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        function switchTab(t, b) {
            document.querySelectorAll('.action-sec, .tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(t + '-sec').classList.add('active');
            b.classList.add('active');
        }
        function copyLink() {
            navigator.clipboard.writeText(window.location.href);
            alert("Payment link copied to clipboard!");
        }
        const createOrder = () => {
            return fetch('/create-order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ amount: document.getElementById('main-amt').value })
            }).then(res => res.json()).then(data => data.id);
        };
        const onApprove = (data) => {
            return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                .then(res => res.json())
                .then(d => { if(d.success) document.getElementById('success-overlay').style.display = 'flex'; });
        };
        paypal.Buttons({ createOrder, onApprove }).render('#paypal-button-container');
        const cardFields = paypal.CardFields({ createOrder, onApprove });
        if (cardFields.isEligible()) {
            const style = { input: { color: 'white', 'font-size': '16px' } };
            cardFields.NumberField({style}).render('#card-number-field');
            cardFields.ExpiryField({style}).render('#card-expiry-field');
            cardFields.CVVField({style}).render('#card-cvv-field');
            document.getElementById('card-btn').addEventListener('click', () => cardFields.submit());
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    balance, history, total_revenue = get_app_data()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=balance, history=history, total_revenue=total_revenue)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = "{:.2f}".format(float(request.json.get('amount', 0)))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": amt}}]}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))￼Enter
