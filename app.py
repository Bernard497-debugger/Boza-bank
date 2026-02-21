import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_KEY', 'KHALI_SECURE_777')
CORS(app)

# --- DATABASE CONFIGURATION ---
# Fix for Render: SQLAlchemy requires 'postgresql://' instead of 'postgres://'
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
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
    fee = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Auto-create tables on startup
with app.app_context():
    db.create_all()

# --- LIVE PAYPAL CONFIG ---
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

# --- UI TEMPLATE ---
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
        .legal-footer { margin-top: 25px; font-size: 11px; color: #444; line-height: 1.4; }
        .legal-link { color: #666; text-decoration: underline; cursor: pointer; }
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
            <div class="history-item">[{{ tx.timestamp.strftime('%H:%M') }}] {{ tx.tx_id }} | +${{ "%.2f"|format(tx.amount) }}</div>
            {% endfor %}
            {% if not history %}
            <div class="history-item" style="opacity: 0.3;">NO RECENT ACTIVITY</div>
            {% endif %}
        </div>
        <div class="disclosure-box">
            <strong>CUSTODY DISCLOSURE:</strong> AuraPay utilizes a 'Pooled Fund' model. Deposits are recorded on our digital ledger while liquidity is secured in our Master Account.
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
            tos: { title: "Terms of Service", body: "AuraPay provides a technical bridge to PayPal. We do not store financial data. Users must ensure recipient details are correct." },
            refund: { title: "Refund Policy", body: "All captured transactions are final. Refunds must be initiated through the merchant or PayPal Resolution Center." }
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
            const label = document.getElementById('dynamic-action-text');
            label.innerText = (mode === 'deposit' ? 'Pay' : 'Send') + ' $' + amt;
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

# --- SEO & VERIFICATION ROUTES ---
@app.route('/google5ce0866dc1e9ca22.html')
def google_verify():
    return "google-site-verification: google5ce0866dc1e9ca22.html"

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://{request.host}/</loc>
            <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>
    </urlset>"""
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response

# --- CORE LOGIC ROUTES ---
@app.route('/')
def index():
    master = UserAccount.query.filter_by(email="master@aurapay").first()
    bal = master.balance if master else 0.0
    history = Transaction.query.order_by(Transaction.timestamp.desc()).limit(10).all()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=bal, history=history)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    base_amount = float(request.args.get('amt', '0.01'))
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
        val = float(res_data['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = val / 1.01
        
        new_tx = Transaction(
            tx_id="AP-" + str(uuid.uuid4())[:8].upper(),
            amount=clean_amt,
            fee=val - clean_amt
        )
        
        master = UserAccount.query.filter_by(email="master@aurapay").first()
        if not master:
            master = UserAccount(email="master@aurapay", balance=0.0)
            db.session.add(master)
            
        master.balance += clean_amt
        db.session.add(new_tx)
        db.session.commit()
        
    return jsonify(res_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
