import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)

# This allows your GitHub site to talk to this Render server
CORS(app)

# 1. SETUP: Pulls your keys from Render's Environment Variables
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')

# URL for Live Payments
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    """Helper to get the PayPal security token."""
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

@app.route('/')
def home():
    """Check this link in your browser to see if server is alive."""
    return "AuraPay Backend is Live! 🚀"

@app.route('/get-config', methods=['GET'])
def get_config():
    """This sends your Client ID to the HTML buttons."""
    if not PAYPAL_CLIENT_ID:
        return jsonify({"error": "PAYPAL_CLIENT_ID is missing in Render settings"}), 500
    return jsonify({"client_id": PAYPAL_CLIENT_ID})

@app.route('/create-order', methods=['POST'])
def create_order():
    """Creates the transaction."""
    token = get_access_token()
    amount = request.args.get('amt', '1.00')
    payee_email = request.args.get('to') 
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount}
        }]
    }
    
    if payee_email:
        payload["purchase_units"][0]["payee"] = {"email_address": payee_email}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    """Finalizes the payment."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers=headers)
    return jsonify(r.json())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
