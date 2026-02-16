import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# YOUR MASTER KEYS (The engine that runs the platform and collects fees)
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
    except: return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | Business Portal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { margin: 0; background: var(--bg); font-family: -apple-system, sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .app-container { width: 92%; max-width: 400px; padding: 40px 30px; border-radius: 40px; background: rgba(255,255,255,0.03); backdrop-filter: blur(50px); border: 1px solid rgba(255,255,255,0.1); text-align: center; position: relative; }
        .logo { font-weight: 900; font-size: 24px; color: var(--accent); margin-bottom: 30px; }
        .payee-tag { font-size: 11px; opacity: 0.4; margin-bottom: 25px; display: block; }
        .amount-input { width: 100%; background: transparent; border: none; color: white; font-size: 3.5rem; font-weight: 800; text-align: center; margin-bottom: 10px; outline: none; }
        .fee-calc { font-size: 10px; opacity: 0.3; margin-bottom: 30px; }
        #onboard-ui { display: {{ 'none' if payee_email else 'flex' }}; flex-direction: column; gap: 15px; }
        .setup-input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; color: white; text-align: center; }
        .setup-btn { background: var(--accent); color: white; border: none; padding: 15px; border-radius: 15px; font-weight: 800; cursor: pointer; }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="logo">AuraPay</div>

        {% if not payee_email %}
        <div id="onboard-ui">
            <p style="font-size:14px; opacity:0.6;">Start receiving payments. No dev account needed.</p>
            <input type="email" id="email-input" class="setup-input" placeholder="Enter PayPal Email">
            <button onclick="window.location.href='/?to='+document.getElementById('email-input').value" class="setup-btn">Create My Terminal</button>
        </div>
        {% else %}
        <div id="terminal-ui">
            <span class="payee-tag">RECIPIENT: {{ payee_email }}</span>
            <input type="number" id="main-amt" class="amount-input" value="100.00" oninput="updateFee(this.value)">
            <div class="fee-calc">Inc. $1.00 platform fee</div>
            <div id="paypal-button-container"></div>
        </div>
        {% endif %}
    </div>

    <script>
        function updateFee(val) {
            const fee = (val * 0.01).toFixed(2);
            document.querySelector('.fee-calc').innerText = `Inc. $${fee} platform fee`;
        }

        if("{{ payee_email }}") {
            paypal.Buttons({
                createOrder: function() {
                    return fetch('/create-order?to={{ payee_email }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('main-amt').value })
                    }).then(res => res.json()).then(data => data.id);
                },
                onApprove: function(data) {
                    return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                        .then(res => res.json()).then(d => { if(d.success) alert("Payment Successful!"); });
                }
            }).render('#paypal-button-container');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    payee_email = request.args.get('to')
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, payee_email=payee_email)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    payee_email = request.args.get('to')
    total_amt = float(request.json.get('amount', 0))
    
    # CALCULATE FEE (1% to you)
    platform_fee = round(total_amt * 0.01, 2)
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD", 
                "value": "{:.2f}".format(total_amt)
            },
            "payee": {"email_address": payee_email},
            "payment_instruction": {
                "disbursement_mode": "INSTANT",
                "platform_fees": [{
                    "amount": {"currency_code": "USD", "value": "{:.2f}".format(platform_fee)}
                }]
            }
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
