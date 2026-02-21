import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_KEY', 'AURA_SECURE_777_KHALI')
CORS(app)

# --- DATABASE CONFIGURATION ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///aurapay.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- SQL MODELS ---
class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id')) # Linked to specific user
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
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

# --- UI TEMPLATE (Exact same UI, but logic is personal) ---
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
        .action-label { font-weight: bold; color: var(--accent); margin-bottom: 5px; font-size: 1.2rem; display: block; }
        .balance-display { background: #000; padding: 10px; border-radius: 10px; border: 1px dashed #333; margin-bottom: 20px; }
        .history-section { text-align: left; margin-top: 20px; border-top: 1px solid #222; padding-top: 15px; font-family: monospace; }
        .history-item { font-size: 10px; color: #888; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="card">
        <h1 style="color: var(--accent); margin-bottom: 5px;">AuraPay</h1>
        <p style="font-size: 10px; color: #444; margin-bottom: 15px;">User: {{ email }}</p>
        <div class="balance-display">
            <span style="font-size: 10px; color: #666;">YOUR AVAILABLE BALANCE</span><br>
            <span style="font-size: 1.2rem; font-weight: bold;">${{ "{:.2f}".format(balance) }}</span>
        </div>
        <input type="number" id="amount" class="amount-input" value="10.00" step="0.01" oninput="updateActionText()">
        <div class="mode-toggle">
            <button id="dep-btn" class="mode-btn active" onclick="setMode('deposit')">Deposit</button>
            <button id="snd-btn" class="mode-btn" onclick="setMode('withdraw')">Withdraw</button>
        </div>
        <span id="dynamic-action-text" class="action-label">Deposit $10.00</span>
        <div id="paypal-button-container"></div>
        <button id="withdraw-btn" style="display:none; width:100%; padding:15px; border-radius:12px; background:var(--accent); color:black; font-weight:bold; border:none;" onclick="handleWithdraw()">Request Withdrawal</button>
        
        <div class="history-section">
            <div style="font-size: 10px; font-weight: bold; margin-bottom: 8px;">MY TRANSACTION HISTORY</div>
            {% for tx in history %}
            <div class="history-item">[{{ tx.timestamp.strftime('%H:%M') }}] {{ tx.tx_id }} | ${{ "%.2f"|format(tx.amount) }}</div>
            {% endfor %}
        </div>
        <br>
        <a href="/logout" style="color:#444; font-size: 10px;">Logout</a>
    </div>

    <script>
        let mode = 'deposit';
        function setMode(m) {
            mode = m;
            document.getElementById('dep-btn').classList.toggle('active', mode === 'deposit');
            document.getElementById('snd-btn').classList.toggle('active', mode === 'withdraw');
            document.getElementById('paypal-button-container').style.display = (mode === 'deposit') ? 'block' : 'none';
            document.getElementById('withdraw-btn').style.display = (mode === 'withdraw') ? 'block' : 'none';
            updateActionText();
        }
        function updateActionText() {
            const amt = document.getElementById('amount').value || "0.00";
            document.getElementById('dynamic-action-text').innerText = (mode === 'deposit' ? 'Deposit' : 'Withdraw') + ' $' + amt;
        }
        function handleWithdraw() {
            const amt = document.getElementById('amount').value;
            fetch('/withdraw', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ amount: amt })
            }).then(res => res.json()).then(data => alert(data.msg));
        }

        paypal.Buttons({
            createOrder: (data, actions) => {
                return fetch('/create-order?amt=' + document.getElementById('amount').value, {method: 'POST'})
                    .then(res => res.json()).then(order => order.id);
            },
            onApprove: (data, actions) => {
                return fetch('/capture/' + data.orderID, {method: 'POST'})
                    .then(() => { location.reload(); });
            }
        }).render('#paypal-button-container');
    </script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = UserAccount.query.get(session['user_id'])
    # Only pull history for this specific user
    history = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.timestamp.desc()).limit(10).all()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=user.balance, email=user.email, history=history)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        user = UserAccount.query.filter_by(email=email).first()
        if not user:
            user = UserAccount(email=email)
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return '<body style="background:#000;color:#fff;text-align:center;padding-top:100px;"><form method="post"><h1>AuraPay</h1><input name="email" placeholder="Email" required><button type="submit">Login</button></form></body>'

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = request.args.get('amt', '10.00')
    total = "{:.2f}".format(float(amt) * 1.01)
    res = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
        headers={"Authorization": f"Bearer {token}"},
        json={"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": total}}]})
    return jsonify(res.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    user = UserAccount.query.get(session['user_id'])
    token = get_access_token()
    res = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}"})
    if res.json().get('status') == 'COMPLETED':
        val = float(res.json()['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = val / 1.01
        user.balance += clean_amt
        db.session.add(Transaction(user_id=user.id, tx_id="AP-"+str(uuid.uuid4())[:8].upper(), amount=clean_amt))
        db.session.commit()
    return jsonify(res.json())

@app.route('/withdraw', methods=['POST'])
def withdraw():
    user = UserAccount.query.get(session['user_id'])
    amt = float(request.json.get('amount', 0))
    if user.balance < amt: return jsonify({"msg": "❌ Insufficient balance"})
    if amt < 5.00: return jsonify({"msg": "❌ Min withdrawal $5.00"})
    
    # Logic: Deduct from their private balance and queue for your review
    user.balance -= amt
    db.session.add(Transaction(user_id=user.id, tx_id="WTH-"+str(uuid.uuid4())[:8].upper(), amount=amt))
    db.session.commit()
    return jsonify({"msg": "✅ Withdrawal requested. Will be processed in 24hrs."})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
