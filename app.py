from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import random
import string
from datetime import datetime, timedelta
import uuid
from supabase_client import supabase_client

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia123-super-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

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
    while supabase_client.room_exists(code):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return code

def calculate_vote_result(room):
    """Hitung hasil voting"""
    votes = room.get("votes", {})
    players = supabase_client.get_players(room["code"])
    players_dict = {p["id"]: p for p in players}
    
    print(f"=== MENGHITUNG VOTE ===")
    print(f"Votes: {votes}")
    print(f"Players sebelum: {[p['name'] for p in players]}")
    
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
        if target_id in players_dict:
            target_name = players_dict[target_id]["name"]
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
        for pid, pdata in players_dict.items():
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
            
            # HAPUS PEMAIN YANG TERELIMINASI (soft delete)
            if eliminated_id:
                print(f"Menghapus pemain: {eliminated} (ID: {eliminated_id})")
                supabase_client.remove_player(eliminated_id, room["code"])
            
            # CEK JUMLAH PEMAIN TERSISA
            remaining = supabase_client.count_active_players(room["code"])
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
                    remaining_players = supabase_client.get_players(room["code"])
                    if remaining_players:
                        new_giver_id = remaining_players[0]["id"]
                        new_giver_name = remaining_players[0]["name"]
                        supabase_client.set_clue_giver(room["code"], new_giver_id, new_giver_name)
                        print(f"Pemberi clue baru: {new_giver_name}")
        
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
        
        # Simpan hasil
        supabase_client.save_result(room["code"], result)
        print(f"Result: {result}")
        return result
        
    else:
        # Hasil seri
        print("Hasil SERI")
        result = {
            "eliminated": "None", 
            "is_impostor": False, 
            "votes": vote_count, 
            "impostor": room.get("impostor_name", "Unknown"),
            "message": "🤝 Hasil seri! Tidak ada yang tereliminasi.",
            "game_continues": True,
            "eliminated_id": None,
            "impostor_wins": False
        }
        supabase_client.save_result(room["code"], result)
        return result

# ================= ROUTES =================
@app.route("/", methods=["GET", "POST"])
def index():
    supabase_client.cleanup_old_rooms()  # Bersihkan room lama
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            return render_template("index.html", error="Nama harus diisi!"), 400
        if len(name) > 20:
            return render_template("index.html", error="Nama terlalu panjang (max 20 karakter)"), 400
        
        # Buat room baru
        code = generate_code()
        player_id = str(uuid.uuid4())
        word = random.choice(words)
        
        # Simpan ke Supabase
        supabase_client.create_room(code, player_id, name, word)
        supabase_client.add_player(player_id, code, name)
        
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
        
        # Cek room
        room = supabase_client.get_room(code)
        if not room:
            return render_template("join.html", error="Room tidak ditemukan!")
        
        if room["game_started"]:
            return render_template("join.html", error="Game sudah dimulai, tidak bisa join!")
        
        # Cek jumlah pemain
        player_count = supabase_client.count_active_players(code)
        if player_count >= 10:
            return render_template("join.html", error="Room sudah penuh (max 10 pemain)!")
        
        if len(name) > 20:
            return render_template("join.html", error="Nama terlalu panjang (max 20 karakter)")
        
        # Cek apakah nama sudah dipakai
        if not supabase_client.is_name_available(code, name):
            return render_template("join.html", error="Nama sudah digunakan dalam room ini!")
        
        # Join room
        player_id = str(uuid.uuid4())
        supabase_client.add_player(player_id, code, name)
        
        # Set session
        session['player_id'] = player_id
        session['room_code'] = code
        session.permanent = True
        
        return redirect(url_for("game", code=code))
    
    return render_template("join.html")

@app.route("/game/<code>")
def game(code):
    # Cek room
    room = supabase_client.get_room(code)
    if not room:
        return render_template("error.html", message="Room tidak ditemukan!"), 404
    
    player_id = session.get('player_id')
    
    # Cek player
    players = supabase_client.get_players(code)
    player_exists = any(p["id"] == player_id for p in players)
    
    if not player_id or not player_exists:
        return redirect(url_for("join"))
    
    # Siapkan data player
    player = next((p for p in players if p["id"] == player_id), None)
    player_name = player["name"] if player else "Unknown"
    players_list = [p["name"] for p in players]
    
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
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    player_id = session.get('player_id')
    players = supabase_client.get_players(code)
    
    # Validasi player
    player_exists = any(p["id"] == player_id for p in players)
    if player_id and not player_exists:
        return jsonify({
            "error": "player_eliminated",
            "message": "Anda telah tereliminasi",
            "redirect": f"/result/{code}"
        }), 403
    
    # Update last activity otomatis oleh Supabase
    
    # CEK JUMLAH PEMAIN TERSISA
    remaining_players = len(players)
    
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
        
        supabase_client.save_result(code, result)
        supabase_client.update_room(code, {"game_started": False})
        
        # Kembalikan response dengan voting_end
        response_data = {
            "players": [{"id": p["id"], "name": p["name"], "is_you": (p["id"] == player_id)} 
                       for p in players],
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
    
    # PROSES COUNTDOWN
    updated_room = supabase_client.decrement_timers(code)
    if updated_room:
        room = updated_room
    
    # Siapkan data pemain
    players_list = [{
        "id": p["id"],
        "name": p["name"],
        "is_you": (p["id"] == player_id)
    } for p in players]
    
    # PROSES VOTING SELESAI
    if room["voting_time"] == 0 and room.get("votes") and room.get("voters"):
        # Voting selesai, hitung hasil
        print(f"Voting selesai di room {code}")
        result = calculate_vote_result(room)
        print(f"Hasil: {result}")
        
        # Update players setelah penghapusan
        players = supabase_client.get_players(code)
        players_list = [{
            "id": p["id"],
            "name": p["name"],
            "is_you": (p["id"] == player_id)
        } for p in players]
        
        # CEK apakah game lanjut atau selesai
        if result["game_continues"]:
            # Game LANJUT ke ronde berikutnya
            print("Game LANJUT ke ronde berikutnya")
            
            # Reset untuk ronde baru
            updates = {
                "game_started": True,
                "clue_time": 20,
                "voting_time": 0,
                "votes": {},
                "voters": []
            }
            
            # Pilih pemberi clue baru
            if players:
                new_giver_id = random.choice([p["id"] for p in players])
                new_giver = next((p for p in players if p["id"] == new_giver_id), None)
                if new_giver:
                    updates["current_clue_giver_id"] = new_giver_id
                    updates["current_clue_giver_name"] = new_giver["name"]
            
            supabase_client.update_room(code, updates)
            room = supabase_client.get_room(code)
            
            response_data = {
                "players": players_list,
                "game_started": True,
                "clue_time": 20,
                "voting_time": 0,
                "current_clue_giver": room.get("current_clue_giver_name"),
                "word_hint": None,
                "votes_cast": 0,
                "total_players": len(players),
                "messages": room.get("messages", [])[-10:],
                "voting_active": False,
                "round_result": result,
                "voters": []
            }
        else:
            # Game SELESAI
            print("Game SELESAI")
            supabase_client.update_room(code, {"game_started": False})
            room = supabase_client.get_room(code)
            
            response_data = {
                "players": players_list,
                "game_started": False,
                "clue_time": 0,
                "voting_time": 0,
                "current_clue_giver": None,
                "word_hint": None,
                "votes_cast": 0,
                "total_players": len(players),
                "messages": room.get("messages", [])[-10:],
                "voting_active": False,
                "voting_end": result,
                "voters": []
            }
        
        # Role info untuk response ini
        if room["game_started"] and player_id:
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
        "votes_cast": len(room.get("voters", [])),
        "total_players": len(players),
        "messages": room.get("messages", [])[-10:],
        "voting_active": room["voting_time"] > 0,
        "voters": room.get("voters", [])
    }
    
    # Role info
    if room["game_started"] and player_id:
        if player_id == room.get("impostor_id"):
            response_data["your_role"] = "IMPOSTOR"
            response_data["word_hint"] = "Kamu adalah IMPOSTOR!"
        else:
            response_data["your_role"] = "CREWMATE"
            response_data["word_hint"] = f"Kata rahasia: {room['word']}"
    
    return jsonify(response_data)

@app.route("/api/start/<code>", methods=["POST"])
def api_start_game(code):
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    player_id = session.get('player_id')
    
    # Cek host
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa memulai game"}), 403
    
    if room["game_started"]:
        return jsonify({"error": "Game sudah dimulai"}), 400
    
    players = supabase_client.get_players(code)
    if len(players) < 2:
        return jsonify({"error": "Minimal 2 pemain"}), 400
    
    # Pilih impostor
    impostor = random.choice(players)
    impostor_id = impostor["id"]
    impostor_name = impostor["name"]
    
    # Pilih pemberi clue pertama
    first_clue_giver = players[0]
    
    # Update room
    supabase_client.start_game(code, impostor_id, impostor_name)
    supabase_client.set_clue_giver(code, first_clue_giver["id"], first_clue_giver["name"])
    
    return jsonify({
        "success": True,
        "message": "Game dimulai!"
    })

@app.route("/api/start-voting/<code>", methods=["POST"])
def api_start_voting(code):
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    player_id = session.get('player_id')
    
    # Cek host
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa memulai voting"}), 403
    
    if not room["game_started"]:
        return jsonify({"error": "Game belum dimulai"}), 400
    
    if room["voting_time"] > 0:
        return jsonify({"error": "Voting sudah berlangsung"}), 400
    
    players = supabase_client.get_players(code)
    
    # Cek apakah masih ada pemain yang bisa vote (minimal 3 pemain)
    if len(players) < 3:
        return jsonify({"error": "Pemain tersisa 2, game akan segera berakhir"}), 400
    
    # Mulai voting
    supabase_client.start_voting(code)
    
    return jsonify({
        "success": True,
        "message": "Voting dimulai!",
        "voting_time": 40
    })

@app.route("/api/vote/<code>", methods=["POST"])
def api_vote(code):
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    data = request.json
    target_name = data.get("target", "").strip()
    voter_id = session.get('player_id')
    
    # Validasi
    if not voter_id:
        return jsonify({"error": "Anda tidak terdaftar"}), 400
    
    players = supabase_client.get_players(code)
    player_exists = any(p["id"] == voter_id for p in players)
    
    if not player_exists:
        return jsonify({"error": "Anda tidak terdaftar di room ini"}), 400
    
    if not room["game_started"]:
        return jsonify({"error": "Game belum dimulai"}), 400
    
    if room["voting_time"] <= 0:
        return jsonify({"error": "Fase voting sudah berakhir"}), 400
    
    if voter_id in room.get("voters", []):
        return jsonify({"error": "Anda sudah melakukan vote"}), 400
    
    # Cari target berdasarkan nama (case insensitive)
    target_id = None
    target_player = None
    for p in players:
        if p["name"].lower() == target_name.lower():
            target_id = p["id"]
            target_player = p
            break
    
    if not target_id:
        return jsonify({"error": "Target tidak ditemukan"}), 400
    
    if target_id == voter_id:
        return jsonify({"error": "Tidak bisa vote diri sendiri"}), 400
    
    # Catat vote
    supabase_client.add_vote(code, voter_id, target_id)
    
    # Hitung jumlah vote yang sudah masuk
    updated_room = supabase_client.get_room(code)
    votes_cast = len(updated_room.get("voters", []))
    
    return jsonify({
        "success": True,
        "message": f"Vote untuk {target_player['name']} tercatat!",
        "votes_cast": votes_cast,
        "total_players": len(players)
    })

@app.route("/api/chat/<code>", methods=["POST"])
def api_chat(code):
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    data = request.json
    message = data.get("message", "").strip()
    player_id = session.get('player_id')
    
    if not player_id:
        return jsonify({"error": "Anda tidak terdaftar"}), 400
    
    players = supabase_client.get_players(code)
    player = next((p for p in players if p["id"] == player_id), None)
    
    if not player:
        return jsonify({"error": "Anda tidak terdaftar"}), 400
    
    if not message or len(message) > 200:
        return jsonify({"error": "Pesan tidak valid"}), 400
    
    # Tambah pesan
    supabase_client.add_message(code, player["name"], message)
    
    return jsonify({"success": True})

@app.route("/result/<code>")
def result(code):
    room = supabase_client.get_room(code)
    if not room:
        return render_template("error.html", message="Room tidak ditemukan"), 404
    
    eliminated = request.args.get("eliminated", "None")
    is_impostor = request.args.get("is_impostor", "false") == "true"
    impostor = request.args.get("impostor", "Unknown")
    message = request.args.get("message", "")
    impostor_wins = request.args.get("impostor_wins", "false") == "true"
    
    player_id = session.get('player_id')
    players = supabase_client.get_players(code)
    
    # Handle jika player_id tidak ada
    player_name = "Unknown"
    is_host = False
    
    if player_id:
        player = next((p for p in players if p["id"] == player_id), None)
        if player:
            player_name = player["name"]
            is_host = (player_id == room["host_id"])
    
    # Jika impostor menang dan ini adalah result terakhir, hapus room setelah dibaca
    if impostor_wins and code:
        # Hapus room setelah 10 detik (kasih waktu client baca)
        import threading
        def delete_room():
            import time
            time.sleep(10)
            supabase_client.delete_room(code)
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
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    player_id = session.get('player_id')
    
    if player_id != room["host_id"]:
        return jsonify({"error": "Hanya host yang bisa merestart game"}), 403
    
    # Reset game
    new_word = random.choice(words)
    supabase_client.reset_game(code, new_word)
    
    return jsonify({"success": True})

@app.route("/api/leave/<code>", methods=["POST"])
def api_leave(code):
    room = supabase_client.get_room(code)
    if not room:
        return jsonify({"error": "Room tidak ditemukan"}), 404
    
    player_id = session.get('player_id')
    
    if not player_id:
        return jsonify({"error": "Anda tidak terdaftar"}), 400
    
    players = supabase_client.get_players(code)
    player_exists = any(p["id"] == player_id for p in players)
    
    if not player_exists:
        return jsonify({"error": "Anda tidak ada di room"}), 400
    
    # Hapus player
    supabase_client.remove_player(player_id, code)
    
    # Cek jumlah player tersisa
    remaining_players = supabase_client.count_active_players(code)
    
    # Jika room kosong, hapus room
    if remaining_players == 0:
        supabase_client.delete_room(code)
        session.clear()
        return jsonify({"success": True, "redirect": "/"})
    
    # Jika host keluar, pilih host baru
    if player_id == room["host_id"]:
        remaining_players_list = supabase_client.get_players(code)
        if remaining_players_list:
            new_host = remaining_players_list[0]
            supabase_client.update_room(code, {
                "host_id": new_host["id"],
                "host_name": new_host["name"]
            })
    
    session.clear()
    return jsonify({"success": True, "redirect": "/"})

if __name__ == "__main__":
    app.run(debug=True)