import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, make_response, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
# Render needs a secret key for sessions to work
app.secret_key = os.environ.get('SESSION_KEY', 'KHALI_SECURE_777_AURA_99')
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
    user_email = db.Column(db.String(120))
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Ensure tables are created before first request
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
    except Exception as e:
        print(f"Token Error: {e}")
        return None

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 10px; text-align: center; }
        .card { background: #111; border: 1px solid #222; padding: 25px; border-radius: 30px; max-width: 400px; margin: 20px auto; }
        .balance-display { background: #000; padding: 15px; border-radius: 15px; border: 1px dashed #333; margin-bottom: 20px; }
        .amount-input { background: transparent; border: none; color: white; font-size: 3rem; width: 100%; text-align: center; outline: none; font-weight: 800; }
        .mode-toggle { display: flex; gap: 10px; margin: 15px 0; }
        .mode-btn { flex: 1; padding: 12px; border-radius: 12px; border: 1px solid #333; background: #1a1a1a; color: white; cursor: pointer; }
        .mode-btn.active { background: var(--accent); color: black; font-weight: bold; }
        .email-field { width: 100%; padding: 15px; border-radius: 12px; border: 1px solid #333; background: #000; color: white; margin-bottom: 15px; display: none; box-sizing: border-box; }
        .action-label { font-weight: bold; color: var(--accent); font-size: 1.1rem; }
        .history-section { text-align: left; margin-top: 20px; border-top: 1px solid #222; padding-top: 15px; }
        .history-item { font-size: 10px; color: #666; margin-bottom: 5px; font-family: monospace; }
        .disclosure-box { font-size: 10px; color: #444; margin-top: 20px; text-align: center; padding: 10px; border-top: 1px solid #222; }
        .legal-link { color: var(--accent); text-decoration: underline; cursor: pointer; font-size: 11px; margin: 0 10px; }
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; }
        .modal-content { background: #111; padding: 30px; border-radius: 20px; text-align: left; max-width: 350px; margin: 100px auto; border: 1px solid #333; }
        .close-btn { background: var(--accent); color: black; border: none; padding: 10px; border-radius: 10px; width: 100%; font-weight: bold; margin-top: 20px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h1 style="color: var(--accent);">AuraPay</h1>
        <div class="balance-display">
            <span style="font-size: 10px; color: #666;">PERSONAL LEDGER</span><br>
            <span style="font-size: 1.5rem; font-weight: bold;">${{ "{:.2f}".format(balance) }}</span>
        </div>
        <input type="number" id="amount" class="amount-input" value="10.00" oninput="updateActionText()">
        <div class="mode-toggle">
            <button id="dep-btn" class="mode-btn active" onclick="setMode('deposit')">Deposit</button>
            <button id="snd-btn" class="mode-btn" onclick="setMode('send')">Send</button>
        </div>
        <input type="email" id="recipient-email" class="email-field" placeholder="Recipient PayPal Email">
        <p id="dynamic-action-text" class="action-label">Pay $10.00</p>
        <div id="paypal-button-container"></div>
        <div class="history-section">
            <div style="font-size: 10px; font-weight: bold; color: #444; margin-bottom: 8px;">MY TRANSACTION HISTORY</div>
            {% for tx in history %}
            <div class="history-item">[{{ tx.timestamp.strftime('%H:%M') }}] {{ tx.tx_id }} | +${{ "%.2f"|format(tx.amount) }}</div>
            {% endfor %}
        </div>
        <div class="disclosure-box">
            <strong>CUSTODY DISCLOSURE:</strong> Funds are secured in our pooled Master Account.
            <div style="margin-top:10px;">
                <span class="legal-link" onclick="openLegal('tos')">Terms of Service</span>
                <span class="legal-link" onclick="openLegal('refund')">Refund Policy</span>
            </div>
        </div>
    </div>
    <div id="legal-modal" class="modal">
        <div class="modal-content">
            <h2 id="modal-title" style="color: var(--accent); margin-top: 0;"></h2>
            <div id="modal-body" style="font-size: 13px; line-height: 1.5; color: #888;"></div>
            <button class="close-btn" onclick="closeLegal()">I UNDERSTAND</button>
        </div>
    </div>
    <script>
        let mode = 'deposit';
        const legalTexts = {
            tos: { title: "Terms of Service", body: "AuraPay acts as a digital ledger for PayPal deposits. Users are responsible for recipient accuracy. All deposits are final once captured." },
            refund: { title: "Refund Policy", body: "Refunds are processed solely through PayPal's resolution center. AuraPay does not hold reversal rights for completed digital captures." }
        };
        function openLegal(type) {
            document.getElementById('modal-title').innerText = legalTexts[type].title;
            document.getElementById('modal-body').innerText = legalTexts[type].body;
            document.getElementById('legal-modal').style.display = 'block';
        }
        function closeLegal() { document.getElementById('legal-modal').style.display = 'none'; }
        function renderButtons() {
            const currentAmt = document.getElementById('amount').value || "0.01";
            const container = document.getElementById('paypal-button-container');
            container.innerHTML = ''; 
            paypal.Buttons({
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
            renderButtons();
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

# --- ROUTES ---
@app.route('/')
def index():
    user_email = session.get('active_user')
    if user_email:
        user = UserAccount.query.filter_by(email=user_email).first()
        bal = user.balance if user else 0.0
        history = Transaction.query.filter_by(user_email=user_email).order_by(Transaction.timestamp.desc()).limit(5).all()
    else:
        bal = 0.0
        history = []
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=bal, history=history)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = float(request.args.get('amt', '10.00'))
    total = "{:.2f}".format(amt * 1.01)
    payee_email = request.args.get('to')
    if payee_email: session['active_user'] = payee_email
    payload = {"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": total}}]}
    if payee_email: payload["purchase_units"][0]["payee"] = {"email_address": payee_email}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    res_data = r.json()
    if res_data.get('status') == 'COMPLETED':
        val = float(res_data['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = val / 1.01
        user_email = session.get('active_user', 'anonymous')
        user = UserAccount.query.filter_by(email=user_email).first()
        if not user:
            user = UserAccount(email=user_email, balance=0.0)
            db.session.add(user)
        user.balance += clean_amt
        db.session.add(Transaction(user_email=user_email, tx_id="AP-"+str(uuid.uuid4())[:8].upper(), amount=clean_amt))
        db.session.commit()
    return jsonify(res_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
