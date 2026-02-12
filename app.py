import os
import uuid
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 🛡️ CREDENTIALS (Set these in Render's Environment tab)
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
ENV = os.environ.get('PAYPAL_ENV', 'sandbox') 
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

def get_real_data():
    """Fetches both Balance and Transaction History from PayPal."""
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Fetch Balance
    balance = "0.00"
    try:
        b_res = requests.get(f"{PAYPAL_BASE_URL}/v1/reporting/balances?currency_code=USD", headers=headers, timeout=10)
        balance = b_res.json()['balances'][0]['total_balance']['value']
    except: pass

    # 2. Fetch Transactions (Last 30 days)
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    history = []
    try:
        t_res = requests.get(
            f"{PAYPAL_BASE_URL}/v1/reporting/transactions?start_date={start_date}&end_date={end_date}&fields=transaction_info", 
            headers=headers, timeout=10
        )
        for tx in t_res.json().get('transaction_details', []):
            info = tx.get('transaction_info', {})
            history.append({
                "type": info.get('transaction_event_code', 'Payment'),
                "amount": float(info.get('transaction_amount', {}).get('value', 0)),
                "date": info.get('transaction_initiation_date', '')[:10]
            })
    except: pass

    return balance, history

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GlassBank Pro</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        body { margin: 0; background: #050505; font-family: 'Inter', sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .app-container { width: 90%; max-width: 400px; padding: 35px; border-radius: 40px; background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(40px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .balance-amount { font-size: 3rem; font-weight: 800; margin: 10px 0 30px 0; background: linear-gradient(to right, #fff, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
        .tabs { display: flex; gap: 10px; margin-bottom: 25px; }
        .tab-btn { flex: 1; padding: 12px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: white; cursor: pointer; }
        .tab-btn.active { background: white; color: black; font-weight: bold; }
        .action-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 25px; display: none; margin-bottom: 20px;}
        .action-card.active { display: block; }
        input { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 15px; color: white; padding: 15px; margin-bottom: 15px; box-sizing: border-box; }
        .send-btn { width: 100%; padding: 16px; border-radius: 15px; border: none; background: #4facfe; color: white; font-weight: bold; cursor: pointer; }
        .history-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }
    </style>
</head>
<body>
    <div class="app-container">
        <div style="text-align:center; opacity:0.5; font-size:12px; letter-spacing:1px;">AVAILABLE BALANCE <button onclick="location.reload()" style="background:none; border:none; color:white; cursor:pointer;">🔄</button></div>
        <div class="balance-amount">${{ balance }}</div>

        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('deposit')">Deposit</button>
            <button class="tab-btn" onclick="showTab('send')">Send</button>
        </div>

        <div id="deposit-tab" class="action-card active">
            <input type="number" id="dep-amt" value="50">
            <div id="paypal-button-container"></div>
        </div>

        <div id="send-tab" class="action-card">
            <input type="email" id="send-email" placeholder="Recipient Email">
            <input type="number" id="send-amt" placeholder="Amount">
            <button class="send-btn" onclick="handleSend()">Confirm Payout</button>
        </div>

        <h4 style="opacity:0.6; margin-top:20px;">Recent Activity</h4>
        {% for item in history %}
        <div class="history-item">
            <span>{{ item.type }} <br><small style="opacity:0.5">{{ item.date }}</small></span>
            <span style="color: {{ '#00ff88' if item.amount > 0 else '#ff4f4f' }}">
                {{ "+" if item.amount > 0 }}{{ "%.2f"|format(item.amount) }}
            </span>
        </div>
        {% endfor %}
    </div>

    <script>
        function showTab(type) {
            document.querySelectorAll('.action-card, .tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(type + '-tab').classList.add('active');
            event.currentTarget.classList.add('active');
        }

        paypal.Buttons({
            createOrder: function() {
                const amt = document.getElementById('dep-amt').value;
                return fetch('/create-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ amount: amt })
                }).then(res => res.json()).then(data => data.id);
            },
            onApprove: function(data) {
                return fetch('/confirm-tx/' + data.orderID, { method: 'POST' }).then(() => location.reload());
            }
        }).render('#paypal-button-container');

        async function handleSend() {
            const email = document.getElementById('send-email').value;
            const amt = document.getElementById('send-amt').value;
            const res = await fetch('/payout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: email, amount: amt })
            });
            if((await res.json()).success) { alert('Sent!'); location.reload(); }
            else { alert('Failed. Check Payouts permissions.'); }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    balance, history = get_real_data()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=balance, history=history)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": request.json.get('amount')}}]}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}"})
    return jsonify({"success": True})

@app.route('/payout', methods=['POST'])
def payout():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "sender_batch_header": {"sender_batch_id": str(uuid.uuid4())},
        "items": [{"recipient_type": "EMAIL", "amount": {"value": str(request.json.get('amount')), "currency": "USD"}, "receiver": request.json.get('email')}]
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v1/payments/payouts", json=payload, headers=headers)
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
