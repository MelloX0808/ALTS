from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

url = "https://qwinrjfvwfjdhxkuzcet.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3aW5yamZ2d2ZqZGh4a3V6Y2V0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc2MjQ4MTMsImV4cCI6MjA5MzIwMDgxM30.KqyoxOCTVwyouPHAdYdjW0oHDYWoU0Cxys1zjUh5Lek" # Use your actual key
supabase: Client = create_client(url, key)

@app.route('/inventory', methods=['GET', 'POST'])
def handle_inventory():
    if request.method == 'GET':
        res = supabase.table('parts').select("id, part_name, brand, category, image_url, quantity, price, threshold").order("id").execute()
        return jsonify(res.data)

    if request.method == 'POST':
        # Check if the incoming request is JSON or a File Form
        if request.is_json:
            data = request.json
        else:
            data = request.form

        action = data.get('action')

        if action == "create":
            image_url = ""
            file = request.files.get('image')
            if file and file.filename != '':
                file_bytes = file.read()
                file_name = file.filename
                supabase.storage.from_("parts_images").upload(
                    file_name, 
                    file_bytes, 
                    {"content-type": file.content_type, "upsert": "true"}
                )
                image_url = supabase.storage.from_("parts_images").get_public_url(file_name)

            new_item = {
                "part_name": data.get('name'),
                "brand": data.get('brand'),
                "category": data.get('category'),
                "image_url": image_url,
                "description": data.get('description'),
                "weight": data.get('weight', ''),
                "dimensions": data.get('dimensions', ''),
                "quantity": int(data.get('qty', 0)),
                "price": float(data.get('price', 0)),
                "threshold": int(data.get('threshold', 0))
            }
            supabase.table('parts').insert(new_item).execute()
            return jsonify({"message": "New part created successfully."})

        if action == "edit":
            p_id = data.get('id')
            updated_fields = {
                "part_name": data.get('name'),
                "brand": data.get('brand'),
                "category": data.get('category'),
                "price": float(data.get('price', 0)),
                "threshold": int(data.get('threshold', 0)),
                "description": data.get('description', '')
            }
            
            file = request.files.get('image')
            if file and file.filename != '':
                file_bytes = file.read()
                file_name = f"updated_{p_id}_{file.filename}"
                supabase.storage.from_("parts_images").upload(
                    file_name, 
                    file_bytes, 
                    {"content-type": file.content_type, "upsert": "true"}
                )
                updated_fields["image_url"] = supabase.storage.from_("parts_images").get_public_url(file_name)

            supabase.table('parts').update(updated_fields).eq("id", p_id).execute()
            return jsonify({"message": "Part information updated successfully."})

        if action == "update":
            p_id = data.get('id')
            amount = data.get('amount')
            # Added 'price' to the select so we can calculate the transaction value
            res = supabase.table('parts').select("id, quantity, part_name, price").eq("id", p_id).execute()
            
            if not res.data:
                return jsonify({"error": "Part not found"}), 404
            
            current_item = res.data[0]
            new_qty = current_item['quantity'] + amount
            
            if new_qty < 0:
                return jsonify({"error": "Stock must not be negative."}), 400
                
            # 1. Update the Part Quantity
            supabase.table('parts').update({"quantity": new_qty}).eq("id", p_id).execute()

            # 2. Log the Transaction (Matching your ERD columns)
            t_type = "RESTOCK" if amount > 0 else "SALE"
            t_data = {
                "part_id": p_id,
                "type": t_type,
                "amount": abs(amount),
                "total_price": abs(amount * current_item.get('price', 0))
            }
            supabase.table('transactions').insert(t_data).execute()

            return jsonify({"item": current_item['part_name'], "new_total": new_qty})

        if action == "delete":
            p_id = data.get('id')
            supabase.table('parts').delete().eq("id", p_id).execute()
            return jsonify({"message": "Part deleted."})

        # --- THE SAFETY NET ---
        # If the action is misspelled or missing, Flask will hit this line instead of crashing!
        return jsonify({"error": f"Invalid or missing action received: {action}"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = data.get('username')
    pwd = data.get('password')
    
    res = supabase.table('users').select("password_hash").eq("username", user).execute()
    
    if not res.data:
        return jsonify({"success": False, "error": "Access denied"}), 401
        
    db_hash = res.data[0]['password_hash']
    
    if check_password_hash(db_hash, pwd):
        return jsonify({"success": True})
        
    return jsonify({"success": False, "error": "Access denied"}), 401

# --- NEW: Fetch Transaction History with Joined Part Name ---
@app.route('/transactions', methods=['GET'])
def get_transactions():
    # Supabase Join: We ask for all transaction data, PLUS the part_name from the linked parts table
    res = supabase.table('transactions').select("*, parts(part_name)").order("created_at", desc=True).limit(20).execute()
    
    # We format the data so the frontend HTML doesn't need to change at all!
    formatted_data = []
    for t in res.data:
        formatted_data.append({
            "created_at": t["created_at"],
            "transaction_type": t["type"],
            "part_name": t["parts"]["part_name"] if t.get("parts") else "Deleted Part",
            "amount": t["amount"],
            "total_value": t["total_price"]
        })
        
    return jsonify(formatted_data)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    user = data.get('username')
    pwd = data.get('password')
    
    # Check if the username is already taken
    existing_user = supabase.table('users').select("id").eq("username", user).execute()
    
    if len(existing_user.data) > 0:
        return jsonify({"success": False, "error": "Username is already taken."}), 400
        
    # Scramble the new password and save to database
    hashed_pwd = generate_password_hash(pwd)
    new_user = {
        "username": user,
        "password_hash": hashed_pwd
    }
    
    supabase.table('users').insert(new_user).execute()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)