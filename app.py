import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# CONFIG
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return response.json().get('access_token')
    except:
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | Global Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: -apple-system, sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 90%; max-width: 400px; padding: 35px; border: 1px solid rgba(255,255,255,0.1); border-radius: 40px; background: rgba(255,255,255,0.02); backdrop-filter: blur(15px); }
        .logo { font-weight: 900; font-size: 26px; color: var(--accent); margin-bottom: 30px; letter-spacing: -1px; }
        
        /* Setup Mode */
        .setup-box { display: flex; flex-direction: column; gap: 15px; }
        .input-text { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 18px; border-radius: 20px; color: white; text-align: center; font-size: 16px; outline: none; }
        .btn { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 20px; font-weight: 800; cursor: pointer; font-size: 16px; }
        
        /* Terminal Mode */
        .recipient-badge { font-size: 11px; color: var(--accent); background: rgba(79,172,254,0.1); padding: 8px 15px; border-radius: 20px; margin-bottom: 20px; display: inline-block; }
        .amount-input { width: 100%; background: transparent; border: none; color: white; font-size: 3.5rem; font-weight: 800; text-align: center; outline: none; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 25px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>

        {% if not payee_email %}
        <div class="setup-box">
            <p style="font-size: 14px; opacity: 0.6;">Enter your PayPal email to create your payment terminal link.</p>
            <input type="email" id="user-email" class="input-text" placeholder="name@example.com">
            <button onclick="launch()" class="btn">Create My Terminal</button>
        </div>
        {% else %}
        <div id="terminal">
            <span class="recipient-badge">Paying: {{ payee_email }}</span>
            <input type="number" id="amt" value="20.00" step="0.01">
            <div id="paypal-button-container"></div>
            <button onclick="copyLink()" style="background:none; border:none; color:white; opacity:0.3; margin-top:25px; cursor:pointer; font-size:12px;">🔗 Copy Shareable Link</button>
        </div>
        {% endif %}
    </div>

    <script>
        function launch() {
            const email = document.getElementById('user-email').value;
            if(email.includes('@')) {
                window.location.href = '/?to=' + encodeURIComponent(email);
            } else {
                alert("Enter a valid email");
            }
        }

        function copyLink() {
            navigator.clipboard.writeText(window.location.href);
            alert("Link copied! Anyone with this link can now pay you.");
        }

        if("{{ payee_email }}") {
            paypal.Buttons({
                createOrder: function() {
                    return fetch('/create-order?to={{ payee_email }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('amt').value })
                    }).then(res => res.json()).then(order => order.id);
                },
                onApprove: function(data) {
                    return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                        .then(res => res.json()).then(result => {
                            if(result.success) alert("Success! Funds sent to {{ payee_email }}");
                        });
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
    amount = request.json.get('amount', '10.00')
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
            "payee": {"email_address": payee_email}
        }]
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers=headers)
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
