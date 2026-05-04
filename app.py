from flask import Flask, request, jsonify

app = Flask(__name__)

# This is the front door (homepage)
@app.route('/')
def home():
    return "<h1>Welcome to the ALTS Engine! The server is running perfectly.</h1>"
# --- Our Mock Database ---
# This acts like our database for now.
# It holds the part ID, its name, the current quantity, and the alert threshold.
mock_db = {
    "1": {"name": "Honda Brake Pad", "quantity": 10, "threshold": 5},
    "2": {"name": "Yamaha Spark Plug", "quantity": 2, "threshold": 10},
    "3": {"name": "Suzuki Oil Filter", "quantity": 25, "threshold": 5}
}

# --- The Route (The "Ear" of the application) ---
# This tells Flask: "If someone sends data to /update-stock, run this function!"
@app.route('/update-stock', methods=['POST'])
def update_stock():
    # 1. Get the data the user sent us
    data = request.get_json()
    part_id = str(data.get("part_id"))
    transaction_type = data.get("type") # Is it "stock-in" or "stock-out"?
    amount = int(data.get("amount", 0))

    # 2. Check if the part exists in our mock database
    if part_id not in mock_db:
        return jsonify({"error": "Part not found!"}), 404

    # 3. Get the current details of the part
    part = mock_db[part_id]
    current_qty = part["quantity"]

    # 4. The Engine Logic! Do the math based on the transaction type.
    if transaction_type == "stock-in":
        new_qty = current_qty + amount
    elif transaction_type == "stock-out":
        # We must prevent "Negative Stock"
        if current_qty - amount < 0:
            return jsonify({"error": "Cannot stock-out more items than available!"}), 400
        new_qty = current_qty - amount
    else:
        return jsonify({"error": "Invalid transaction type. Must be 'stock-in' or 'stock-out'"}), 400

    # 5. Save the new quantity back to our mock database
    mock_db[part_id]["quantity"] = new_qty

    # 6. Check the Automated Low-Stock Alert Engine
    # Is the new quantity lower than the threshold?
    alert_triggered = False
    if new_qty <= part["threshold"]:
        alert_triggered = True

    # 7. Send the response back to the user's screen
    response = {
        "message": f"Successfully updated {part['name']}.",
        "new_quantity": new_qty,
        "low_stock_alert": alert_triggered
    }
    
    return jsonify(response), 200

# This starts the Flask server
if __name__ == '__main__':
    # Running on port 5000 by default
    app.run(debug=True)