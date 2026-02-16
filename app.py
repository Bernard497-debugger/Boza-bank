import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay | Public Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: -apple-system, sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; overflow: hidden; }
        .container { width: 92%; max-width: 400px; padding: 40px 25px; border-radius: 40px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(15px); }
        .logo { font-weight: 900; font-size: 28px; color: var(--accent); margin-bottom: 5px; }
        .tagline { font-size: 10px; opacity: 0.4; letter-spacing: 3px; margin-bottom: 30px; display: block; }
        
        .main-input { width: 100%; background: transparent; border: none; color: white; font-size: 4rem; font-weight: 800; text-align: center; outline: none; }
        .email-input { width: 85%; background: #111; border: 1px solid #333; padding: 18px; border-radius: 20px; color: white; text-align: center; font-size: 16px; margin-bottom: 15px; }
        
        .label { font-size: 10px; opacity: 0.4; font-weight: bold; margin-bottom: 5px; display: block; }
        .btn { background: var(--accent); color: #000; border: none; padding: 18px; border-radius: 20px; font-weight: 800; width: 100%; cursor: pointer; font-size: 16px; transition: 0.3s; }
        .btn:active { transform: scale(0.98); opacity: 0.8; }
        
        #setup-ui, #register-ui, #success-screen { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>
        <span class="tagline">TERMINAL ENGINE</span>

        <div id="setup-ui">
            <p style="font-size: 14px; opacity: 0.6; margin-bottom: 25px;">Enter your PayPal email to receive payments on this device.</p>
            <input type="email" id="merchant-email" class="email-input" placeholder="email@example.com">
            <button onclick="saveAndStart()" class="btn">Start Receiving</button>
        </div>

        <div id="register-ui">
            <span class="label">SALE AMOUNT (USD)</span>
            <input type="number" id="sale-amt" class="main-input" value="10.00" step="0.01">
            <p id="display-email" style="font-size: 11px; opacity: 0.4; margin-bottom: 25px;"></p>
            
            <div id="paypal-button-container"></div>
            
            <button onclick="logout()" style="background:none; border:none; color:white; opacity:0.2; margin-top:40px; cursor:pointer; font-size:12px;">SWITCH ACCOUNT</button>
        </div>

        <div id="success-screen">
            <div style="font-size:60px; color:var(--accent);">✓</div>
            <h2 style="margin:10px 0;">PAYMENT SUCCESS</h2>
            <button onclick="resetTerminal()" class="btn" style="margin-top:20px;">Next Sale</button>
        </div>
    </div>

    <script>
        const setupUI = document.getElementById('setup-ui');
        const registerUI = document.getElementById('register-ui');
        const successUI = document.getElementById('success-screen');

        // On Load: Check if we have a saved email
        window.onload = function() {
            const savedEmail = localStorage.getItem('aurapay_email');
            if (savedEmail) {
                launchTerminal(savedEmail);
            } else {
                setupUI.style.display = 'block';
            }
        };

        function saveAndStart() {
            const email = document.getElementById('merchant-email').value;
            if(email.includes('@')) {
                localStorage.setItem('aurapay_email', email);
                launchTerminal(email);
            } else {
                alert("Please enter a valid email.");
            }
        }

        function launchTerminal(email) {
            setupUI.style.display = 'none';
            registerUI.style.display = 'block';
            document.getElementById('display-email').innerText = "Receiver: " + email;
            renderButtons(email);
        }

        function logout() {
            localStorage.removeItem('aurapay_email');
            location.reload();
        }

        function resetTerminal() {
            successUI.style.display = 'none';
            registerUI.style.display = 'block';
        }

        function renderButtons(merchantEmail) {
            document.getElementById('paypal-button-container').innerHTML = "";
            paypal.Buttons({
                style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'pay' },
                createOrder: async function() {
                    const res = await fetch('/create-order?to=' + encodeURIComponent(merchantEmail), {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('sale-amt').value })
                    });
                    const data = await res.json();
                    return data.id;
                },
                onApprove: async function(data) {
                    const res = await fetch('/confirm-tx/' + data.orderID, { method: 'POST' });
                    const result = await res.json();
                    if(result.success) {
                        registerUI.style.display = 'none';
                        successUI.style.display = 'block';
                    }
                }
            }).render('#paypal-button-container');
        }
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
    
    merchant_email = request.args.get('to')
    amount = request.json.get('amount', '10.00')
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": "{:.2f}".format(float(amount))},
            "payee": {"email_address": merchant_email}
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
                     json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
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
