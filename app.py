import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- LIVE CONFIG ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return res.json().get('access_token')
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay | Secure Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; --card-bg: #111; }
        body { background: var(--bg); color: white; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; text-align: center; }
        .card { background: var(--card-bg); border: 1px solid #222; padding: 30px; border-radius: 35px; max-width: 400px; margin: 0 auto; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
        .logo { color: var(--accent); font-weight: 900; font-size: 2rem; margin-bottom: 5px; letter-spacing: -1px; }
        .status-badge { font-size: 10px; background: rgba(0,255,136,0.1); color: var(--accent); padding: 4px 12px; border-radius: 20px; letter-spacing: 2px; text-transform: uppercase; }
        
        .amount-input { background: transparent; border: none; color: white; font-size: 4rem; width: 100%; text-align: center; outline: none; margin: 20px 0; font-weight: 800; }
        
        .mode-toggle { display: flex; gap: 10px; margin-bottom: 25px; background: #000; padding: 5px; border-radius: 18px; border: 1px solid #222; }
        .mode-btn { flex: 1; padding: 12px; border-radius: 14px; border: none; background: transparent; color: #666; cursor: pointer; transition: 0.3s; font-weight: 600; }
        .mode-btn.active { background: var(--accent); color: black; }
        
        .email-field { width: 100%; padding: 18px; border-radius: 15px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; display: none; box-sizing: border-box; font-size: 16px; }
        
        .action-label { font-weight: 700; color: var(--accent); margin-bottom: 15px; font-size: 1.1rem; display: block; opacity: 0.9; }
        #paypal-button-container { min-height: 150px; }

        .legal-footer { margin-top: 25px; font-size: 11px; color: #555; line-height: 1.5; }
        .legal-link { color: #888; text-decoration: underline; cursor: pointer; }

        /* Modal Logic */
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:9999; overflow-y: auto; padding: 20px; box-sizing: border-box;}
        .modal-content { background: #1a1a1a; padding: 30px; border-radius: 25px; text-align: left; max-width: 500px; margin: 40px auto; border: 1px solid #333; }
        .close-modal { background: var(--accent); color: black; border: none; padding: 10px 20px; border-radius: 10px; font-weight: bold; width: 100%; margin-top: 20px; }
    </style>
</head>
<body>

    <div class="card">
        <div class="logo">AuraPay</div>
        <span class="status-badge">Live Terminal</span>

        <input type="number" id="amount" class="amount-input" value="0.01" step="0.01" oninput="updateActionText()">

        <div class="mode-toggle">
            <button id="dep-btn" class="mode-btn active" onclick="setMode('deposit')">Deposit</button>
            <button id="snd-btn" class="mode-btn" onclick="setMode('send')">Send</button>
        </div>

        <input type="email" id="recipient-email" class="email-field" placeholder="Enter recipient email">

        <span id="dynamic-action-text" class="action-label">Pay $0.01</span>

        <div id="paypal-button-container"></div>

        <div class="legal-footer">
            By proceeding, you agree to our <br>
            <span class="legal-link" onclick="openModal('tos')">Terms of Service</span> & 
            <span class="legal-link" onclick="openModal('refund')">Refund Policy</span>
        </div>
    </div>

    <div id="legalModal" class="modal">
        <div class="modal-content">
            <h2 id="modalTitle" style="color:var(--accent)"></h2>
            <div id="modalBody" style="font-size: 14px; line-height: 1.6; color: #ccc;"></div>
            <button class="close-modal" onclick="closeModal()">I Understand</button>
        </div>
    </div>

    <script>
        let mode = 'deposit';

        function updateActionText() {
            const amt = document.getElementById('amount').value || "0.00";
            const label = document.getElementById('dynamic-action-text');
            const verb = (mode === 'deposit') ? 'Pay' : 'Send';
            label.innerText = `${verb} $${amt}`;
        }

        function setMode(newMode) {
            mode = newMode;
            document.getElementById('dep-btn').classList.toggle('active', mode === 'deposit');
            document.getElementById('snd-btn').classList.toggle('active', mode === 'send');
            document.getElementById('recipient-email').style.display = (mode === 'send') ? 'block' : 'none';
            updateActionText();
        }

        // Modal Content
        const legalData = {
            tos: {
                title: "Terms of Service",
                body: "AuraPay is a technical bridge powered by PayPal. We do not store card data or manage funds directly. Users are responsible for providing correct recipient emails. Unauthorized use for illegal activities is strictly prohibited. Transactions are subject to PayPal's standard merchant fees."
            },
            refund: {
                title: "Refund Policy",
                body: "All transactions are final once captured. Refunds must be requested directly from the recipient merchant via the PayPal Resolution Center. AuraPay cannot reverse processed payments as funds move directly through the PayPal network."
            }
        };

        function openModal(type) {
            document.getElementById('modalTitle').innerText = legalData[type].title;
            document.getElementById('modalBody').innerText = legalData[type].body;
            document.getElementById('legalModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('legalModal').style.display = 'none';
        }

        paypal.Buttons({
            style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'pay' },
            createOrder: function(data, actions) {
                const amt = document.getElementById('amount').value;
                const email = document.getElementById('recipient-email').value;
                let url = '/create-order?amt=' + amt;
                if(mode === 'send' && email) url += '&to=' + encodeURIComponent(email);

                return fetch(url, { method: 'POST' })
                    .then(res => res.json())
                    .then(order => order.id);
            },
            onApprove: function(data, actions) {
                return fetch('/capture/' + data.orderID, { method: 'POST' })
                    .then(res => res.json())
                    .then(() => {
                        alert('Transaction Complete! Check your PayPal account for details.');
                        location.reload();
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
    amount = request.args.get('amt', '0.01')
    payee_email = request.args.get('to')
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": "USD", "value": amount}}]
    }
    if payee_email:
        payload["purchase_units"][0]["payee"] = {"email_address": payee_email}
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
