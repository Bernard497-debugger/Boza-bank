import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, session
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_KEY', 'KHALI_SECURE_777') # Needed for Ledger
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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 20px; text-align: center; }
        .card { background: #111; border: 1px solid #222; padding: 30px; border-radius: 30px; max-width: 400px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .amount-input { background: transparent; border: none; color: white; font-size: 3.5rem; width: 100%; text-align: center; outline: none; margin: 10px 0; font-weight: 800; }
        .mode-toggle { display: flex; gap: 10px; margin-bottom: 20px; }
        .mode-btn { flex: 1; padding: 10px; border-radius: 12px; border: 1px solid #333; background: #1a1a1a; color: white; cursor: pointer; transition: 0.2s; }
        .mode-btn.active { background: var(--accent); color: black; border-color: var(--accent); font-weight: bold; }
        .email-field { width: 100%; padding: 15px; border-radius: 12px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; display: none; box-sizing: border-box; }
        
        .action-label { font-weight: bold; color: var(--accent); margin-bottom: 5px; font-size: 1.2rem; display: block; }
        .fee-label { font-size: 11px; color: #666; margin-bottom: 15px; }
        
        #paypal-button-container { min-height: 150px; }

        /* LEDGER & DISCLOSURE STYLES */
        .balance-display { background: #000; padding: 10px; border-radius: 10px; border: 1px dashed #333; margin-bottom: 20px; }
        .history-section { text-align: left; margin-top: 20px; border-top: 1px solid #222; padding-top: 15px; font-family: monospace; }
        .history-item { font-size: 10px; color: #888; margin-bottom: 5px; }

        .legal-footer { margin-top: 25px; font-size: 11px; color: #444; line-height: 1.4; }
        .legal-link { color: #666; text-decoration: underline; cursor: pointer; }
        .disclosure-box { font-size: 9px; color: #333; margin-top: 15px; text-align: justify; line-height: 1.2; border-top: 1px solid #222; padding-top: 10px;}
        
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; padding: 20px; box-sizing: border-box; }
        .modal-content { background: #1a1a1a; padding: 25px; border-radius: 20px; text-align: left; max-width: 400px; margin: 50px auto; border: 1px solid #333; }
        .close-btn { background: var(--accent); color: black; border: none; padding: 10px; border-radius: 10px; width: 100%; font-weight: bold; margin-top: 15px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h1 style="color: var(--accent); margin-bottom: 5px;">AuraPay</h1>
        
        <div class="balance-display">
            <span style="font-size: 10px; color: #666;">AVAILABLE BALANCE</span><br>
            <span style="font-size: 1.2rem; font-weight: bold;">${{ "{:.2f}".format(balance) }}</span>
        </div>

        <input type="number" id="amount" class="amount-input" value="10.00" step="0.01" oninput="updateActionText()">

        <div class="mode-toggle">
            <button id="dep-btn" class="mode-btn active" onclick="setMode('deposit')">Deposit</button>
            <button id="snd-btn" class="mode-btn" onclick="setMode('send')">Send</button>
        </div>

        <input type="email" id="recipient-email" class="email-field" placeholder="Recipient PayPal Email">

        <span id="dynamic-action-text" class="action-label">Pay $10.00</span>
        <div class="fee-label">+ 1% Institutional Processing Fee</div>

        <div id="paypal-button-container"></div>

        <div class="history-section">
            <div style="font-size: 10px; font-weight: bold; margin-bottom: 8px;">TRANSACTION HISTORY</div>
            {% for tx in history %}
            <div class="history-item">[{{ tx.date }}] {{ tx.id }} | +${{ tx.amt }}</div>
            {% endfor %}
            {% if not history %}
            <div class="history-item" style="opacity: 0.3;">NO RECENT ACTIVITY</div>
            {% endif %}
        </div>

        <div class="disclosure-box">
            <strong>CUSTODY DISCLOSURE:</strong> AuraPay utilizes a 'Pooled Fund' model. 
            Deposits are recorded on our digital ledger while fiat liquidity is secured 
            in our Master Business Account to facilitate instant features.
        </div>

        <div class="legal-footer">
            By proceeding, you agree to our <br>
            <span class="legal-link" onclick="openLegal('tos')">Terms of Service</span> & 
            <span class="legal-link" onclick="openLegal('refund')">Refund Policy</span>
        </div>
    </div>

    <div id="legal-modal" class="modal">
        <div class="modal-content">
            <h2 id="modal-title" style="color: var(--accent); margin-top: 0;"></h2>
            <div id="modal-body" style="font-size: 13px; line-height: 1.6; color: #bbb;"></div>
            <button class="close-btn" onclick="closeLegal()">I AGREE</button>
        </div>
    </div>

    <script>
        let mode = 'deposit';
        let typingTimer;

        const legalTexts = {
            tos: {
                title: "Terms of Service",
                body: "AuraPay provides a technical bridge to PayPal. We do not store financial data or CVVs. Users must ensure recipient details are correct. Transaction fees are governed by PayPal's merchant rates."
            },
            refund: {
                title: "Refund Policy",
                body: "All captured transactions are final. Refunds must be initiated through the merchant or the PayPal Resolution Center. AuraPay does not hold or manage your funds."
            }
        };

        function openLegal(type) {
            document.getElementById('modal-title').innerText = legalTexts[type].title;
            document.getElementById('modal-body').innerText = legalTexts[type].body;
            document.getElementById('legal-modal').style.display = 'block';
        }

        function closeLegal() {
            document.getElementById('legal-modal').style.display = 'none';
        }

        function renderButtons() {
            const currentAmt = document.getElementById('amount').value || "0.01";
            const container = document.getElementById('paypal-button-container');
            container.innerHTML = ''; 

            paypal.Buttons({
                commit: true, 
                style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'pay' },
                createOrder: function(data, actions) {
                    const email = document.getElementById('recipient-email').value;
                    let url = '/create-order?amt=' + currentAmt;
                    if(mode === 'send' && email) url += '&to=' + encodeURIComponent(email);

                    return fetch(url, { method: 'POST' })
                        .then(res => res.json())
                        .then(order => order.id);
                },
                onApprove: function(data, actions) {
                    return fetch('/capture/' + data.orderID, { method: 'POST' })
                        .then(res => res.json())
                        .then(() => {
                            location.reload();
                        });
                }
            }).render('#paypal-button-container');
        }

        function updateActionText() {
            const amt = document.getElementById('amount').value || "0.00";
            const label = document.getElementById('dynamic-action-text');
            const verb = (mode === 'deposit') ? 'Pay' : 'Send';
            label.innerText = `${verb} $${amt}`;

            clearTimeout(typingTimer);
            typingTimer = setTimeout(renderButtons, 500);
        }

        function setMode(newMode) {
            mode = newMode;
            document.getElementById('dep-btn').classList.toggle('active', mode === 'deposit');
            document.getElementById('snd-btn').classList.toggle('active', mode === 'send');
            document.getElementById('recipient-email').style.display = (mode === 'send') ? 'block' : 'none';
            updateActionText();
        }

        window.onload = renderButtons;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    if 'balance' not in session: session['balance'] = 0.00
    if 'history' not in session: session['history'] = []
    return render_template_string(HTML_TEMPLATE, 
                                client_id=PAYPAL_CLIENT_ID, 
                                balance=session['balance'], 
                                history=session['history'])

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    base_amount = float(request.args.get('amt', '0.01'))
    
    # Logic: Charge 1% extra for your platform
    total_charged = "{:.2f}".format(base_amount * 1.01)
    
    payee_email = request.args.get('to')
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": total_charged},
            "description": "AuraPay Digital Service"
        }]
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
    
    res_data = r.json()
    if res_data.get('status') == 'COMPLETED':
        # Update session ledger
        val = float(res_data['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = val / 1.01 # Remove fee for user balance
        
        session['balance'] += clean_amt
        new_tx = {
            "id": "TX-" + str(uuid.uuid4())[:6].upper(),
            "date": datetime.now().strftime("%H:%M"),
            "amt": "{:.2f}".format(clean_amt)
        }
        session['history'].insert(0, new_tx)
        session.modified = True
        
    return jsonify(res_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
