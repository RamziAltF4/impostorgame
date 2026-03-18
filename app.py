from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import random
import string
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia123-super-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

rooms = {}
words = [
    "Pizza", "Kucing", "Mobil", "Laptop", "Buku", "Gitar", "Sepeda", "Kopi",
    "Matahari", "Bulan", "Bintang", "Hujan", "Angin", "Gunung", "Pantai", "Laut",
    "Komputer", "HP", "Televisi", "Radio", "Sepatu", "Baju", "Topi", "Kacamata","Jepang","Bali","Kipas"
]

# ================= UTILITY =================
def generate_code():
    """Generate kode room unik 6 karakter"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    while code in rooms:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return code

def calculate_vote_result(room):
    """Hitung hasil voting dengan sistem yang lebih baik"""
    votes = room.get("votes", {})
    
    if not votes:
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": {}, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "Tidak ada voting yang dilakukan"
        }

    # Hitung suara per target (berdasarkan target_id)
    vote_count = {}
    for voter_id, target_id in votes.items():
        # Dapatkan nama target
        if target_id in room["players"]:
            target_name = room["players"][target_id]["name"]
            vote_count[target_name] = vote_count.get(target_name, 0) + 1
    
    if not vote_count:
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": {}, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "Tidak ada suara valid"
        }

    max_votes = max(vote_count.values())
    losers = [p for p, v in vote_count.items() if v == max_votes]

    if len(losers) == 1:
        eliminated = losers[0]
        is_impostor = (eliminated == room.get("impostor_name"))
        
        if is_impostor:
            message = f"🎉 {eliminated} adalah IMPOSTOR! Crewmate menang!"
        else:
            message = f"😢 {eliminated} adalah CREWMATE. Impostor masih hidup!"
            
        return {
            "eliminated": eliminated, 
            "is_impostor": is_impostor, 
            "votes": vote_count, 
            "impostor": room["impostor_name"],
            "message": message
        }
    else:
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": vote_count, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "🤝 Hasil seri! Tidak ada yang tereliminasi."
        }

def cleanup_old_rooms():
    """Bersihkan room yang sudah tidak aktif"""
    current_time = datetime.now()
    to_delete = []
    for code, room in rooms.items():
        if 'last_activity' in room:
            if current_time - room['last_activity'] > timedelta(hours=2):
                to_delete.append(code)
    
    for code in to_delete:
        del rooms[code]

# ================= ROUTES =================
@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_old_rooms()  # Bersihkan room lama
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            return render_template("index.html", error="Nama harus diisi!"), 400
        if len(name) > 20:
            return render_template("index.html", error="Nama terlalu panjang (max 20 karakter)"), 400
        
        # Buat room baru
        code = generate_code()
        player_id = str(uuid.uuid4())
        
        rooms[code] = {
            "host_id": player_id,
            "host_name": name,
            "players": {player_id: {"name": name, "joined_at": datetime.now()}},
            "word": random.choice(words),
            "impostor_id": None,
            "impostor_name": None,
            "votes": {},
            "voters": set(),
            "game_started": False,
            "clue_time": 0,
            "voting_time": 0,
            "current_clue_giver_id": player_id,
            "current_clue_giver_name": name,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "messages": []
        }
        
        # Set session
        session['player_id'] = player_id
        session['room_code'] = code
        session.permanent = True
        
        return redirect(url_for("game", code=code))
    
    return render_template("index.html")

@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        
        if not code or not name:
            return render_template("join.html", error="Kode room dan nama harus diisi!")
        if code not in rooms:
            return render_template("join.html", error="Room tidak ditemukan!")
        
        room = rooms[code]
        if room["game_started"]:
            return render_template("join.html", error="Game sudah dimulai, tidak bisa join!")
        
        if len(room["players"]) >= 10:
            return render_template("join.html", error="Room sudah penuh (max 10 pemain)!")
        
        if len(name) > 20:
            return render_template("join.html", error="Nama terlalu panjang (max 20 karakter)")
        
        # Cek apakah nama sudah dipakai
        for player in room["players"].values():
            if player["name"].lower() == name.lower():
                return render_template("join.html", error="Nama sudah digunakan dalam room ini!")
        
        # Join room
        player_id = str(uuid.uuid4())
        room["players"][player_id] = {"name": name, "joined_at": datetime.now()}
        room["last_activity"] = datetime.now()
        
        # Set session
        session['player_id'] = player_id
        session['room_code'] = code
        session.permanent = True
        
        return redirect(url_for("game", code=code))
    
    return render_template("join.html")

@app.route("/game/<code>")
def game(code):
    # Cek room
    if code not in rooms:
        return render_template("error.html", message="Room tidak ditemukan!"), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Cek player
    if not player_id or player_id not in room["players"]:
        return redirect(url_for("join"))
    
    # Update last activity
    room["last_activity"] = datetime.now()
    
    # Siapkan data player
    player_name = room["players"][player_id]["name"]
    players_list = [p["name"] for p in room["players"].values()]
    
    return render_template(
        "game.html",
        code=code,
        name=player_name,
        player_id=player_id,
        players=players_list,
        host_name=room["host_name"],
        is_host=(player_id == room["host_id"])
    )

@app.route("/api/status/<code>")
def api_status(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Update last activity
    room["last_activity"] = datetime.now()
    
    # Siapkan data pemain
    players_list = [{
        "id": pid,
        "name": data["name"],
        "is_you": (pid == player_id)
    } for pid, data in room["players"].items()]
    
    # Timer logic - HAPUS auto voting, hanya countdown
    response_data = {
        "players": players_list,
        "game_started": room["game_started"],
        "clue_time": room["clue_time"],
        "voting_time": room["voting_time"],
        "current_clue_giver": room.get("current_clue_giver_name"),
        "word_hint": None,
        "votes_cast": len(room.get("voters", set())),
        "total_players": len(room["players"]),
        "messages": room.get("messages", [])[-10:],
        "voting_active": room["voting_time"] > 0  # Tambah flag voting aktif
    }
    
    # Role info (hanya untuk player sendiri)
    if room["game_started"]:
        if player_id == room.get("impostor_id"):
            response_data["your_role"] = "IMPOSTOR"
            response_data["word_hint"] = "Kamu adalah IMPOSTOR!"
        else:
            response_data["your_role"] = "CREWMATE"
            response_data["word_hint"] = f"Kata rahasia: {room['word']}"
    
    # Countdown clue time (jika ada)
    if room["game_started"] and room["clue_time"] > 0:
        room["clue_time"] -= 1
    
    # Countdown voting time (jika sedang voting)
    if room["voting_time"] > 0:
        room["voting_time"] -= 1
        if room["voting_time"] == 0:
            # Voting selesai, hitung hasil
            result = calculate_vote_result(room)
            response_data["voting_end"] = result
            room["game_started"] = False
            room["votes"] = {}
            room["voters"] = set()
            room["clue_time"] = 0
            room["voting_time"] = 0
    
    return jsonify(response_data)

@app.route("/api/start/<code>", methods=["POST"])
def api_start_game(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Cek host
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa memulai game"}), 403
    
    if room["game_started"]:
        return jsonify({"error": "Game sudah dimulai"}), 400
    
    if len(room["players"]) < 2:
        return jsonify({"error": "Minimal 2 pemain"}), 400
    
    # Pilih impostor
    impostor_id = random.choice(list(room["players"].keys()))
    impostor_name = room["players"][impostor_id]["name"]
    
    room["game_started"] = True
    room["impostor_id"] = impostor_id
    room["impostor_name"] = impostor_name
    room["clue_time"] = 20
    room["voting_time"] = 0
    
    # Pilih pemberi clue pertama
    first_clue_giver_id = list(room["players"].keys())[0]
    room["current_clue_giver_id"] = first_clue_giver_id
    room["current_clue_giver_name"] = room["players"][first_clue_giver_id]["name"]
    
    # Reset votes
    room["votes"] = {}
    room["voters"] = set()
    
    return jsonify({
        "success": True,
        "message": "Game dimulai!"
    })

@app.route("/api/start-voting/<code>", methods=["POST"])
def api_start_voting(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Cek host
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa memulai voting"}), 403
    
    if not room["game_started"]:
        return jsonify({"error": "Game belum dimulai"}), 400
    
    if room["voting_time"] > 0:
        return jsonify({"error": "Voting sudah berlangsung"}), 400
    
    # Mulai voting
    room["voting_time"] = 30  # 60 detik voting
    room["clue_time"] = 0  # Hentikan fase clue
    room["votes"] = {}
    room["voters"] = set()
    
    return jsonify({
        "success": True,
        "message": "Voting dimulai!",
        "voting_time": room["voting_time"]
    })

@app.route("/api/chat/<code>", methods=["POST"])
def api_chat(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    data = request.json
    message = data.get("message", "").strip()
    player_id = session.get('player_id')
    
    if not player_id or player_id not in room["players"]:
        return jsonify({"error": "Anda tidak terdaftar"}), 400
    
    if not message or len(message) > 200:
        return jsonify({"error": "Pesan tidak valid"}), 400
    
    player_name = room["players"][player_id]["name"]
    
    # Tambah pesan
    if "messages" not in room:
        room["messages"] = []
    
    room["messages"].append({
        "name": player_name,
        "message": message,
        "time": datetime.now().strftime("%H:%M")
    })
    
    # Batasi jumlah pesan
    if len(room["messages"]) > 50:
        room["messages"] = room["messages"][-50:]
    
    return jsonify({"success": True})

@app.route("/result/<code>")
def result(code):
    if code not in rooms:
        return render_template("error.html", message="Room tidak ditemukan"), 404
    
    eliminated = request.args.get("eliminated", "None")
    is_impostor = request.args.get("is_impostor", "false") == "true"
    impostor = request.args.get("impostor", "Unknown")
    message = request.args.get("message", "")
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Handle jika player_id tidak ada di session
    player_name = "Unknown"
    is_host = False
    
    if player_id and player_id in room["players"]:
        player_name = room["players"][player_id]["name"]
        is_host = (player_id == room["host_id"])
    
    return render_template(
        "result.html", 
        code=code, 
        eliminated=eliminated, 
        is_impostor=is_impostor, 
        impostor=impostor,
        message=message,
        player_name=player_name,
        is_host=is_host
    )

@app.route("/api/restart/<code>", methods=["POST"])
def api_restart(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa merestart game"}), 403
    
    # Reset game
    room["word"] = random.choice(words)
    room["impostor_id"] = None
    room["impostor_name"] = None
    room["votes"] = {}
    room["voters"] = set()
    room["game_started"] = False
    room["clue_time"] = 0
    room["voting_time"] = 0
    room["messages"] = []
    
    return jsonify({"success": True})

@app.route("/api/leave/<code>", methods=["POST"])
def api_leave(code):
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    if not player_id or player_id not in room["players"]:
        return jsonify({"error": "Anda tidak ada di room"}), 400
    
    # Hapus player
    del room["players"][player_id]
    
    # Jika room kosong, hapus room
    if len(room["players"]) == 0:
        del rooms[code]
        session.clear()
        return jsonify({"success": True, "redirect": "/"})
    
    # Jika host keluar, pilih host baru
    if player_id == room["host_id"] and room["players"]:
        new_host_id = list(room["players"].keys())[0]
        room["host_id"] = new_host_id
        room["host_name"] = room["players"][new_host_id]["name"]
    
    session.clear()
    return jsonify({"success": True, "redirect": "/"})

if __name__ == "__main__":
    app.run(debug=True)