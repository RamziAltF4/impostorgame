from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import random
import string
from datetime import datetime, timedelta
import uuid
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia123-super-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Deteksi environment (Vercel atau local)
is_vercel = os.environ.get('VERCEL', False) or os.environ.get('VERCEL_ENV', False)

if is_vercel:
    # Untuk Vercel (HTTPS)
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True
else:
    # Untuk Local (HTTP)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_DOMAIN'] = None

rooms = {}
words = [
    "Pensil", "Pulpen", "Buku", "Kertas", "Meja", "Kursi", "Lemari", "Kasur",
    "Bantal", "Guling", "Sprei", "Karpet", "Piring", "Gelas", "Sendok", "Garpu",
    "Pisau", "Panci", "Wajan", "Ember", "Sapu", "Pel", "Lap", "Kain",
    "Tali", "Benang", "Jarum", "Gunting", "Lem", "Karet", "Plastik", "Kardus",
    "Tidur", "Duduk", "Berdiri", "Jalan", "Lari", "Lompat", "Makan", "Minum",
    "Masak", "Goreng", "Rebus", "Bakar", "Cuci", "Setrika", "Sapu", "Pel",
    "HP", "TV", "Radio", "Laptop", "Komputer", "Tablet", "Charger", "Kabel",
    "Lampu", "Kipas", "AC", "Kulkas", "Kompor", "Tabung", "Gas",
    "Spidol", "Kapur", "Penghapus", "Rautan", "Penggaris", "Jangka", "Busur",
    "Stabilo", "Tinta", "Klip", "Stapler", "Peta", "Amplop",
    "Bola", "Raket", "Net", "Gawang", "Ring", "Tali", "Jaring", "Bet",
    "Mobil", "Motor", "Becak", "Delman", "Kereta", "Bus", "Truk", "Pickup",
    "Baju", "Celana", "Topi", "Sepatu", "Kaos", "Jaket", "Sarung", "Peci",
    "Kemeja", "Rok", "Daster", "Jilbab", "Kerudung", "Hijab", "Sandal", "Selop",
    "Nasi", "Roti", "Mie", "Telur", "Tahu", "Tempe", "Ikan", "Daging",
    "Ayam", "Bebek", "Kambing", "Sapi", "Bakso", "Soto", "Sate", "Gado",
    "Pecel", "Rawon", "Rendang", "Gulai", "Sop", "Sayur", "Lalap", "Sambal", "Jepang", 
    "Bali", "Kediri", "Malang", "Wonosobo", "Bawang", "Merah", "Tunjang"
]

# ================= UTILITY =================
def generate_code():
    """Generate kode room unik 6 karakter"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    while code in rooms:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return code

def calculate_vote_result(room):
    """Hitung hasil voting"""
    votes = room.get("votes", {})
    print(f"=== MENGHITUNG VOTE ===")
    print(f"Votes: {votes}")
    print(f"Players sebelum: {[p['name'] for p in room['players'].values()]}")
    
    if not votes:
        print("Tidak ada vote")
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": {}, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "Tidak ada voting yang dilakukan",
            "game_continues": True,
            "eliminated_id": None,
            "impostor_wins": False
        }

    # Hitung suara per target
    vote_count = {}
    for voter_id, target_id in votes.items():
        if target_id in room["players"]:
            target_name = room["players"][target_id]["name"]
            vote_count[target_name] = vote_count.get(target_name, 0) + 1
    
    print(f"Vote count: {vote_count}")
    
    if not vote_count:
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": {}, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "Tidak ada suara valid",
            "game_continues": True,
            "eliminated_id": None,
            "impostor_wins": False
        }

    max_votes = max(vote_count.values())
    losers = [p for p, v in vote_count.items() if v == max_votes]
    print(f"Losers: {losers}, max_votes: {max_votes}")

    if len(losers) == 1:
        eliminated = losers[0]
        is_impostor = (eliminated == room.get("impostor_name"))
        print(f"Eliminated: {eliminated}, is_impostor: {is_impostor}")
        
        # Cari ID pemain yang tereliminasi
        eliminated_id = None
        for pid, pdata in list(room["players"].items()):
            if pdata["name"] == eliminated:
                eliminated_id = pid
                break
        
        if is_impostor:
            message = f"🎉 {eliminated} adalah IMPOSTOR! Crewmate menang!"
            game_continues = False
            impostor_wins = False
            print("IMPOSTOR tertangkap! Game selesai.")
        else:
            message = f"😢 {eliminated} adalah Warga. Impostor masih berkeliaran!"
            
            # HAPUS PEMAIN YANG TERELIMINASI
            if eliminated_id:
                print(f"Menghapus pemain: {eliminated} (ID: {eliminated_id})")
                del room["players"][eliminated_id]
            
            # CEK JUMLAH PEMAIN TERSISA
            remaining = len(room["players"])
            print(f"Pemain tersisa: {remaining}")
            
            if remaining <= 2:
                # Jika pemain tersisa 2 atau kurang, impostor menang
                impostor_name = room.get("impostor_name", "Unknown")
                message = f"🏆 {impostor_name} adalah IMPOSTOR dan menang! Pemain tersisa {remaining}."
                game_continues = False
                impostor_wins = True
                print(f"Impostor MENANG! Sisa pemain: {remaining}")
            else:
                game_continues = True
                impostor_wins = False
                print(f"Game LANJUT dengan {remaining} pemain")
                
                # Update current_clue_giver jika yang tereliminasi adalah pemberi clue
                if eliminated_id == room.get("current_clue_giver_id"):
                    if room["players"]:
                        new_giver_id = list(room["players"].keys())[0]
                        room["current_clue_giver_id"] = new_giver_id
                        room["current_clue_giver_name"] = room["players"][new_giver_id]["name"]
                        print(f"Pemberi clue baru: {room['current_clue_giver_name']}")
        
        result = {
            "eliminated": eliminated, 
            "is_impostor": is_impostor, 
            "votes": vote_count, 
            "impostor": room["impostor_name"],
            "message": message,
            "game_continues": game_continues,
            "eliminated_id": eliminated_id,
            "impostor_wins": impostor_wins
        }
        print(f"Result: {result}")
        return result
        
    else:
        # Hasil seri
        print("Hasil SERI")
        return {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": vote_count, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "🤝 Hasil seri! Tidak ada yang tereliminasi.",
            "game_continues": True,
            "eliminated_id": None,
            "impostor_wins": False
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
    # Ambil player_id dari query parameter (untuk Vercel) atau session
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    
    # Validasi player
    if not player_id or player_id not in room["players"]:
        return jsonify({
            "error": "player_eliminated",
            "message": "Anda telah tereliminasi",
            "redirect": f"/result/{code}"
        }), 403
    
    # Update last activity
    room["last_activity"] = datetime.now()
    
    # CEK JUMLAH PEMAIN TERSISA
    remaining_players = len(room["players"])
    
    # Jika game sedang berjalan dan pemain tersisa 2
    if room["game_started"] and remaining_players == 2:
        # Impostor menang
        impostor_name = room.get("impostor_name", "Unknown")
        result = {
            "eliminated": "None",
            "is_impostor": True,
            "impostor": impostor_name,
            "message": f"🏆 {impostor_name} adalah IMPOSTOR dan menang! Pemain tersisa 2.",
            "game_continues": False,
            "impostor_wins": True
        }
        
        room["last_result"] = result
        room["game_started"] = False
        
        # Kembalikan response dengan voting_end
        response_data = {
            "players": [{"id": pid, "name": pdata["name"], "is_you": (pid == player_id)} 
                       for pid, pdata in room["players"].items()],
            "game_started": False,
            "clue_time": 0,
            "voting_time": 0,
            "current_clue_giver": None,
            "word_hint": None,
            "votes_cast": 0,
            "total_players": remaining_players,
            "messages": room.get("messages", [])[-10:],
            "voting_active": False,
            "voting_end": result,
            "voters": []
        }
        return jsonify(response_data)
    
    # Siapkan data pemain
    players_list = [{
        "id": pid,
        "name": data["name"],
        "is_you": (pid == player_id)
    } for pid, data in room["players"].items()]
    
    # PROSES COUNTDOWN
    if room["game_started"] and room["clue_time"] > 0:
        room["clue_time"] -= 1
    
    # PROSES VOTING SELESAI
    if room["voting_time"] > 0:
        room["voting_time"] -= 1
        if room["voting_time"] == 0:
            # Voting selesai, hitung hasil
            print(f"Voting selesai di room {code}")
            result = calculate_vote_result(room)
            print(f"Hasil: {result}")
            
            room["last_result"] = result
            
            # Update players_list setelah penghapusan
            players_list = [{
                "id": pid,
                "name": data["name"],
                "is_you": (pid == player_id)
            } for pid, data in room["players"].items()]
            
            # CEK apakah game lanjut atau selesai
            if result["game_continues"]:
                # Game LANJUT dengan ronde baru
                print("Game LANJUT ke ronde berikutnya")
                room["game_started"] = True
                room["clue_time"] = 20
                room["voting_time"] = 0
                room["votes"] = {}
                room["voters"] = set()
                
                # Pilih pemberi clue baru
                if room["players"]:
                    new_giver_id = random.choice(list(room["players"].keys()))
                    room["current_clue_giver_id"] = new_giver_id
                    room["current_clue_giver_name"] = room["players"][new_giver_id]["name"]
                
                response_data = {
                    "players": players_list,
                    "game_started": True,
                    "clue_time": 20,
                    "voting_time": 0,
                    "current_clue_giver": room.get("current_clue_giver_name"),
                    "word_hint": None,
                    "votes_cast": 0,
                    "total_players": len(room["players"]),
                    "messages": room.get("messages", [])[-10:],
                    "voting_active": False,
                    "round_result": result,
                    "voters": []
                }
            else:
                # Game SELESAI
                print("Game SELESAI")
                room["game_started"] = False
                response_data = {
                    "players": players_list,
                    "game_started": False,
                    "clue_time": 0,
                    "voting_time": 0,
                    "current_clue_giver": None,
                    "word_hint": None,
                    "votes_cast": 0,
                    "total_players": len(room["players"]),
                    "messages": room.get("messages", [])[-10:],
                    "voting_active": False,
                    "voting_end": result,
                    "voters": []
                }
            
            # Role info untuk response ini
            if room["game_started"]:
                if player_id == room.get("impostor_id"):
                    response_data["your_role"] = "IMPOSTOR"
                    response_data["word_hint"] = "Kamu adalah IMPOSTOR!"
                else:
                    response_data["your_role"] = "CREWMATE"
                    response_data["word_hint"] = f"Kata rahasia: {room['word']}"
            
            return jsonify(response_data)
    
    # RESPONSE DEFAULT (tidak ada voting selesai)
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
        "voting_active": room["voting_time"] > 0,
        "voters": list(room.get("voters", set()))
    }
    
    # Role info
    if room["game_started"]:
        if player_id == room.get("impostor_id"):
            response_data["your_role"] = "IMPOSTOR"
            response_data["word_hint"] = "Kamu adalah IMPOSTOR!"
        else:
            response_data["your_role"] = "CREWMATE"
            response_data["word_hint"] = f"Kata rahasia: {room['word']}"
    
    return jsonify(response_data)

@app.route("/api/start/<code>", methods=["POST"])
def api_start_game(code):
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    
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
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    
    # Cek host
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa memulai voting"}), 403
    
    if not room["game_started"]:
        return jsonify({"error": "Game belum dimulai"}), 400
    
    if room["voting_time"] > 0:
        return jsonify({"error": "Voting sudah berlangsung"}), 400
    
    # Cek apakah masih ada pemain yang bisa vote (minimal 3 pemain)
    if len(room["players"]) < 3:
        return jsonify({"error": "Pemain tersisa 2, game akan segera berakhir"}), 400
    
    # Mulai voting
    room["voting_time"] = 40
    room["clue_time"] = 0
    room["votes"] = {}
    room["voters"] = set()
    
    return jsonify({
        "success": True,
        "message": "Voting dimulai!",
        "voting_time": room["voting_time"]
    })

@app.route("/api/vote/<code>", methods=["POST"])
def api_vote(code):
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    data = request.json
    target_name = data.get("target", "").strip()
    
    # Validasi
    if not player_id or player_id not in room["players"]:
        return jsonify({"error": "Anda tidak terdaftar di room ini"}), 400
    
    if not room["game_started"]:
        return jsonify({"error": "Game belum dimulai"}), 400
    
    if room["voting_time"] <= 0:
        return jsonify({"error": "Fase voting sudah berakhir"}), 400
    
    if player_id in room.get("voters", set()):
        return jsonify({"error": "Anda sudah melakukan vote"}), 400
    
    # Cari target berdasarkan nama (case insensitive)
    target_id = None
    for pid, pdata in room["players"].items():
        if pdata["name"].lower() == target_name.lower():
            target_id = pid
            break
    
    if not target_id:
        return jsonify({"error": "Target tidak ditemukan"}), 400
    
    if target_id == player_id:
        return jsonify({"error": "Tidak bisa vote diri sendiri"}), 400
    
    # Catat vote
    room["votes"][player_id] = target_id
    room["voters"] = room.get("voters", set())
    room["voters"].add(player_id)
    
    return jsonify({
        "success": True,
        "message": f"Vote untuk {target_name} tercatat!",
        "votes_cast": len(room["voters"]),
        "total_players": len(room["players"])
    })

@app.route("/api/chat/<code>", methods=["POST"])
def api_chat(code):
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    data = request.json
    message = data.get("message", "").strip()
    
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
    impostor_wins = request.args.get("impostor_wins", "false") == "true"
    
    room = rooms[code]
    player_id = session.get('player_id')
    
    # Handle jika player_id tidak ada di session
    player_name = "Unknown"
    is_host = False
    
    if player_id and player_id in room["players"]:
        player_name = room["players"][player_id]["name"]
        is_host = (player_id == room["host_id"])
    
    # Jika impostor menang dan ini adalah result terakhir, hapus room setelah dibaca
    if impostor_wins and code in rooms:
        # Hapus room setelah 10 detik (kasih waktu client baca)
        import threading
        def delete_room():
            import time
            time.sleep(10)
            if code in rooms:
                del rooms[code]
        threading.Thread(target=delete_room).start()
    
    return render_template(
        "result.html", 
        code=code, 
        eliminated=eliminated, 
        is_impostor=is_impostor, 
        impostor=impostor,
        message=message,
        player_name=player_name,
        is_host=is_host,
        impostor_wins=impostor_wins
    )

@app.route("/api/restart/<code>", methods=["POST"])
def api_restart(code):
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    
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
    # Ambil player_id dari query parameter
    player_id = request.args.get('player_id') or session.get('player_id')
    
    if code not in rooms:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    room = rooms[code]
    
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