import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
# If you are testing with Sandbox keys, change this to api-m.sandbox.paypal.com
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        return res.json().get('access_token') if res.status_code == 200 else None
    except: return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay | Simple Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 90%; max-width: 400px; padding: 40px 20px; border-radius: 30px; background: #111; border: 1px solid #222; }
        .logo { font-weight: 900; font-size: 24px; color: var(--accent); margin-bottom: 30px; }
        .amount-input { width: 100%; background: transparent; border: none; color: white; font-size: 4rem; font-weight: 800; text-align: center; outline: none; margin-bottom: 20px; }
        .label { font-size: 10px; opacity: 0.5; letter-spacing: 2px; }
        #paypal-button-container { min-height: 150px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>
        <span class="label">PAYMENT AMOUNT (USD)</span>
        <input type="number" id="amt" value="10.00" class="amount-input">
        
        <div id="paypal-button-container"></div>
    </div>

    <script>
        paypal.Buttons({
            style: { layout: 'vertical', color: 'gold', shape: 'pill', label: 'checkout' },
            createOrder: function(data, actions) {
                return fetch('/create-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ amount: document.getElementById('amt').value })
                })
                .then(res => res.json())
                .then(order => {
                    if (!order.id) {
                        alert("PayPal rejected the request. Check Render logs.");
                        return;
                    }
                    return order.id;
                });
            },
            onApprove: function(data, actions) {
                return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                .then(res => res.json())
                .then(result => {
                    if(result.success) alert("Payment Received!");
                });
            }
        }).render('#paypal-button-container');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    if not token: return jsonify({"error": "Auth Failed"}), 401
    
    amount = request.json.get('amount', '10.00')
    
    # Simple payload WITHOUT payee routing
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD",
                "value": "{:.2f}".format(float(amount))
            }
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
                     json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    
    if r.status_code != 201:
        print(f"PAYPAL ERROR: {r.text}")
        
    return jsonify(r.json()), r.status_code

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
