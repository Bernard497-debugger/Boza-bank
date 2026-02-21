import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, make_response, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
# The secret key makes the user's session untamperable
app.secret_key = os.environ.get('SESSION_KEY', 'KHALI_SECURE_777_AURA')
CORS(app)

# --- DATABASE CONFIGURATION ---
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///aurapay.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- SQL MODELS ---
class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120)) # Hidden filter field
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
    fee = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- LIVE PAYPAL CONFIG ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        res = requests.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'}, timeout=10)
        return res.json().get('access_token')
    except: return None

# --- UI TEMPLATE (As requested: NO UI EDITS) ---
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
        .balance-display { background: #000; padding: 10px; border-radius: 10px; border: 1px dashed #333; margin-bottom: 20px; }
        .history-section { text-align: left; margin-top: 20px; border-top: 1px solid #222; padding-top: 15px; font-family: monospace; }
        .history-item { font-size: 10px; color: #888; margin-bottom: 5px; }
        .disclosure-box { font-size: 9px; color: #333; margin-top: 15px; text-align: justify; line-height: 1.2; border-top: 1px solid #222; padding-top: 10px;}
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
            <div class="history-item">[{{ tx.timestamp.strftime('%H:%M') }}] {{ tx.tx_id }} | +${{ "%.2f"|format(tx.amount) }}</div>
            {% endfor %}
            {% if not history %}
            <div class="history-item" style="opacity: 0.3;">NO RECENT ACTIVITY</div>
            {% endif %}
        </div>
        <div class="disclosure-box">
            <strong>CUSTODY DISCLOSURE:</strong> AuraPay utilizes a 'Pooled Fund' model. Deposits are recorded on our digital ledger while liquidity is secured in our Master Account.
        </div>
    </div>
    <script>
        let mode = 'deposit';
        let typingTimer;
        function renderButtons() {
            const currentAmt = document.getElementById('amount').value || "0.01";
            const container = document.getElementById('paypal-button-container');
            container.innerHTML = ''; 
            paypal.Buttons({
                style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'pay' },
                createOrder: function(data, actions) {
                    const email = document.getElementById('recipient-email').value;
                    let url = '/create-order?amt=' + currentAmt;
                    if(mode === 'send' && email) url += '&to=' + encodeURIComponent(email);
                    return fetch(url, { method: 'POST' }).then(res => res.json()).then(order => order.id);
                },
                onApprove: function(data, actions) {
                    return fetch('/capture/' + data.orderID, { method: 'POST' })
                        .then(res => res.json()).then(() => { location.reload(); });
                }
            }).render('#paypal-button-container');
        }
        function updateActionText() {
            const amt = document.getElementById('amount').value || "0.00";
            document.getElementById('dynamic-action-text').innerText = (mode === 'deposit' ? 'Pay' : 'Send') + ' $' + amt;
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

# --- LOGIC TO HIDE LEDGER ---
@app.route('/')
def index():
    # We check the browser session for an active user email
    user_email = session.get('active_user')
    
    if user_email:
        # Show ONLY this user's balance and history
        user = UserAccount.query.filter_by(email=user_email).first()
        bal = user.balance if user else 0.0
        history = Transaction.query.filter_by(user_email=user_email).order_by(Transaction.timestamp.desc()).limit(10).all()
    else:
        # If no session, show $0.00. The Master Ledger stays secret.
        bal = 0.0
        history = []
        
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=bal, history=history)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = float(request.args.get('amt', '0.01'))
    total = "{:.2f}".format(amt * 1.01)
    
    payee_email = request.args.get('to')
    # Save the email in the session so they see their own balance after capture
    if payee_email:
        session['active_user'] = payee_email

    payload = {"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": total}}]}
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
        val = float(res_data['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = val / 1.01
        user_email = session.get('active_user', 'anonymous')
        
        # 1. Update Personal Ledger
        user = UserAccount.query.filter_by(email=user_email).first()
        if not user:
            user = UserAccount(email=user_email, balance=0.0)
            db.session.add(user)
        user.balance += clean_amt
        
        # 2. Record Transaction for that user
        db.session.add(Transaction(user_email=user_email, tx_id="AP-"+str(uuid.uuid4())[:8].upper(), amount=clean_amt))
        db.session.commit()
        
    return jsonify(res_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
