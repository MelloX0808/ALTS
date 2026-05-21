from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Use your actual key
url = "https://qwinrjfvwfjdhxkuzcet.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3aW5yamZ2d2ZqZGh4a3V6Y2V0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc2MjQ4MTMsImV4cCI6MjA5MzIwMDgxM30.KqyoxOCTVwyouPHAdYdjW0oHDYWoU0Cxys1zjUh5Lek" 
supabase: Client = create_client(url, key)

@app.route('/inventory', methods=['GET', 'POST'])
def handle_inventory():
    if request.method == 'GET':
        res = supabase.table('parts').select("*").order("id").execute()
        return jsonify(res.data)

    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        action = data.get('action')

        if action == "create":
            new_item = {
                "part_name": data.get('name'), "brand": data.get('brand'), "category": data.get('category'),
                "description": data.get('description', ''), "quantity": int(data.get('qty', 0)),
                "price": float(data.get('price', 0)), "threshold": int(data.get('threshold', 0))
            }
            # Handle Image Upload if exists
            file = request.files.get('image') if not request.is_json else None
            if file and file.filename != '':
                supabase.storage.from_("parts_images").upload(file.filename, file.read(), {"content-type": file.content_type, "upsert": "true"})
                new_item["image_url"] = supabase.storage.from_("parts_images").get_public_url(file.filename)
            
            supabase.table('parts').insert(new_item).execute()
            return jsonify({"message": "Part created"})

        if action == "edit":
            p_id = data.get('id')
            updated = {"part_name": data.get('name'), "brand": data.get('brand'), "category": data.get('category'), "price": float(data.get('price', 0)), "description": data.get('description', '')}
            file = request.files.get('image') if not request.is_json else None
            if file and file.filename != '':
                file_name = f"updated_{p_id}_{file.filename}"
                supabase.storage.from_("parts_images").upload(file_name, file.read(), {"content-type": file.content_type, "upsert": "true"})
                updated["image_url"] = supabase.storage.from_("parts_images").get_public_url(file_name)
            supabase.table('parts').update(updated).eq("id", p_id).execute()
            return jsonify({"message": "Part updated"})

        if action == "edit_stock":
            supabase.table('parts').update({"quantity": int(data.get('qty', 0)), "threshold": int(data.get('threshold', 0))}).eq("id", data.get('id')).execute()
            return jsonify({"message": "Stock updated"})

        if action == "update":
            p_id = data.get('id')
            current = supabase.table('parts').select("quantity").eq("id", p_id).execute().data[0]
            supabase.table('parts').update({"quantity": current['quantity'] + data.get('amount')}).eq("id", p_id).execute()
            return jsonify({"status": "success"})

        if action == "delete_item":
            p_id = data.get('id')
            supabase.table('transactions').delete().eq("part_id", p_id).execute()
            supabase.table('parts').delete().eq("id", p_id).execute()
            return jsonify({"message": "Part deleted"})

        return jsonify({"error": "Invalid action"}), 400

@app.route('/transactions', methods=['GET', 'POST'])
def get_transactions():
    if request.method == 'GET':
        return jsonify(supabase.table('transactions').select("*").order("created_at", desc=True).execute().data)
    if request.method == 'POST':
        data = request.json
        supabase.table('transactions').insert({"part_id": data.get("part_id"), "type": data.get("type"), "amount": data.get("amount"), "total_price": data.get("total_price")}).execute()
        return jsonify({"status": "success"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    res = supabase.table('users').select("password_hash").eq("username", data.get('username')).execute()
    if not res.data or not check_password_hash(res.data[0]['password_hash'], data.get('password')):
        return jsonify({"success": False, "error": "Access denied"}), 401
    return jsonify({"success": True})

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if len(supabase.table('users').select("id").eq("username", data.get('username')).execute().data) > 0:
        return jsonify({"success": False, "error": "Username taken"}), 400
    supabase.table('users').insert({"username": data.get('username'), "password_hash": generate_password_hash(data.get('password'))}).execute()
    return jsonify({"success": True})

# --- ADMIN VERIFIED PASSWORD CHANGE ---
@app.route('/change-password', methods=['POST'])
def change_password():
    data = request.json
    user = data.get('username')
    new_pwd = data.get('new_password')
    admin_code = data.get('admin_code')

    # Security Check: Must match this exact string to authorize
    if admin_code != "ADMIN-ALTS-2026":
        return jsonify({"success": False, "error": "Invalid Admin Confirmation Code."}), 403

    hashed_pwd = generate_password_hash(new_pwd)
    res = supabase.table('users').update({"password_hash": hashed_pwd}).eq("username", user).execute()

    if len(res.data) > 0:
        return jsonify({"success": True, "message": "Password securely updated."})
    return jsonify({"success": False, "error": "User not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)