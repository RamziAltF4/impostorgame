from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import random
import string
import time
from threading import Thread, Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia123'
app.config['DEBUG'] = True

# SocketIO dengan konfigurasi khusus untuk development
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',  # Paksa pakai threading
    logger=True,  # Aktifkan logging
    engineio_logger=True  # Aktifkan logging Engine.IO
)

# Database
rooms = {}
words = ["Pizza", "Kucing", "Mobil", "Laptop", "Buku", "Gitar", "Sepeda", "Kopi"]
room_locks = {}  # Untuk thread safety

# ===================== TIMER FUNCTIONS =====================
def clue_timer(code):
    """Timer untuk memberikan clue (10 detik)"""
    print(f"🎯 CLUE TIMER STARTED for room {code}")
    
    # Cek room masih ada
    if code not in rooms:
        print(f"❌ Room {code} not found")
        return
    
    # Cek timer aktif
    if code not in room_locks:
        room_locks[code] = Lock()
    
    with room_locks[code]:
        room = rooms[code]
        if room.get("timer_active", False):
            print(f"⏰ Timer already active for room {code}")
            return
        room["timer_active"] = True
    
    try:
        # Dapatkan nama pemain pertama untuk clue giver
        players_list = list(room["players"].values())
        clue_giver = players_list[0] if players_list else "Someone"
        room["current_clue_giver"] = clue_giver
        
        print(f"📢 Clue giver: {clue_giver}")
        
        # Kirim timer setiap detik
        for i in range(20, 0, -1):
            if code not in rooms:
                print(f"❌ Room {code} deleted during timer")
                return
            
            print(f"⏱️ Sending clue timer: {i} to room {code}")
            
            # Emit ke semua client di room
            socketio.emit("clue_timer", {
                "time": i,
                "current_player": clue_giver
            }, room=code)
            
            # Tunggu 1 detik (tanpa blocking event loop)
            socketio.sleep(1)
        
        # Setelah clue timer selesai
        if code in rooms:
            print(f"✅ Clue timer finished for room {code}, starting voting")
            socketio.emit("start_voting", {}, room=code)
            
            # Mulai voting timer
            socketio.start_background_task(voting_timer, code)
            
    except Exception as e:
        print(f"❌ Error in clue timer: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if code in rooms:
            with room_locks[code]:
                rooms[code]["timer_active"] = False
            print(f"🔄 Timer reset for room {code}")

def voting_timer(code):
    """Timer untuk voting (15 detik)"""
    print(f"🎯 VOTING TIMER STARTED for room {code}")
    
    if code not in rooms:
        print(f"❌ Room {code} not found")
        return
    
    try:
        for i in range(60, 0, -1):
            if code not in rooms:
                return
            
            print(f"⏱️ Sending voting timer: {i} to room {code}")
            socketio.emit("voting_timer", {"time": i}, room=code)
            socketio.sleep(1)
        
        # Voting selesai
        if code in rooms:
            print(f"✅ Voting timer finished for room {code}")
            room = rooms[code]
            
            # Hitung hasil
            votes = room.get("votes", {})
            print(f"📊 Final votes: {votes}")
            
            # Tentukan hasil
            result = calculate_vote_result(room, votes)
            print(f"🏆 Result: {result}")
            
            # Kirim hasil
            socketio.emit("voting_end", result, room=code)
            
            # Reset untuk game berikutnya
            room["votes"] = {}
            room["game_started"] = False
            
    except Exception as e:
        print(f"❌ Error in voting timer: {e}")
        import traceback
        traceback.print_exc()

def calculate_vote_result(room, votes):
    """Hitung hasil voting"""
    if not votes:
        return {
            "eliminated": None,
            "is_impostor": False,
            "votes": {},
            "impostor": room.get("impostor_name", "Unknown")
        }
    
    max_votes = max(votes.values())
    losers = [p for p, v in votes.items() if v == max_votes]
    
    if len(losers) == 1:
        eliminated = losers[0]
        is_impostor = (eliminated == room.get("impostor_name"))
        
        return {
            "eliminated": eliminated,
            "is_impostor": is_impostor,
            "votes": votes,
            "impostor": room["impostor_name"] if not is_impostor else eliminated
        }
    else:
        return {
            "eliminated": None,
            "is_impostor": False,
            "votes": votes,
            "impostor": room.get("impostor_name", "Unknown")
        }

# ===================== ROUTES =====================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            return "Nama harus diisi!", 400
        
        code = generate_code()
        rooms[code] = {
            "host_name": name,
            "host_sid": None,
            "players": {},
            "word": random.choice(words),
            "impostor_sid": None,
            "impostor_name": None,
            "votes": {},
            "timer_active": False,
            "current_clue_giver": name,
            "game_started": False
        }
        return redirect(url_for("game", code=code, name=name))
    
    return render_template("index.html")

@app.route("/game/<code>")
def game(code):
    if code not in rooms:
        return "Room tidak ditemukan!", 404
    
    name = request.args.get("name")
    if not name:
        return redirect(url_for("index"))
    
    room = rooms[code]
    players = list(room["players"].values())
    print(f"🏠 GAME PAGE - Code: {code}")
    print(f"   Name: {name}")
    print(f"   Host: {room['host_name']}")
    print(f"   Players from room: {players}")
    print(f"   Player count: {len(players)}")
    
    return render_template("game.html", 
                         code=code, 
                         name=name, 
                         players=players,
                         host_name=room["host_name"],
                         is_host=(name == room["host_name"]),
                        player_count=len(players))

@app.route("/result/<code>")
def result(code):
    if code not in rooms:
        return "Room tidak ditemukan!", 404
    
    eliminated = request.args.get("eliminated", "None")
    is_impostor = request.args.get("is_impostor", "false") == "true"
    impostor = request.args.get("impostor", "Unknown")
    
    return render_template("result.html",
                         code=code,
                         eliminated=eliminated,
                         is_impostor=is_impostor,
                         impostor=impostor)

# ===================== UTILITY =====================
def generate_code():
    code = ''.join(random.choices(string.ascii_uppercase, k=5))
    while code in rooms:
        code = ''.join(random.choices(string.ascii_uppercase, k=5))
    return code

# ===================== SOCKET EVENTS =====================
@socketio.on("connect")
def handle_connect():
    print(f"🔌 Client connected: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")
    # Handle disconnect...

@socketio.on("join_room")
def handle_join(data):
    code = data.get("code")
    name = data.get("name")
    
    print(f"📥 Join request - Code: {code}, Name: {name}, SID: {request.sid}")
    
    if not code or not name:
        emit("error", {"msg": "Data tidak lengkap!"}, to=request.sid)
        return
    
    if code not in rooms:
        emit("error", {"msg": "Room tidak ditemukan!"}, to=request.sid)
        return
    
    room = rooms[code]
    join_room(code)
    
    # Simpan player
    room["players"][request.sid] = name
    
    # Jika host, simpan SID
    if name == room["host_name"] and room["host_sid"] is None:
        room["host_sid"] = request.sid
        print(f"⭐ Host SID saved: {request.sid}")
    
    # Update semua player
    players_list = list(room["players"].values())
    print(f"👥 Players in room {code}: {players_list}")
    
    socketio.emit("update_players", players_list, room=code)
    emit("join_success", {"code": code, "name": name}, to=request.sid)

@socketio.on("start_game")
def handle_start_game(data):
    code = data.get("code")
    
    print(f"🎮 Start game request - Code: {code}, SID: {request.sid}")
    
    if code not in rooms:
        emit("error", {"msg": "Room tidak ditemukan!"}, to=request.sid)
        return
    
    room = rooms[code]
    
    # Cek host
    if request.sid != room.get("host_sid"):
        emit("error", {"msg": "Hanya host yang bisa memulai game!"}, to=request.sid)
        return
    
    # Cek jumlah pemain
    players = list(room["players"].keys())
    if len(players) < 2:
        emit("error", {"msg": "Minimal 2 pemain!"}, to=request.sid)
        return
    
    if room.get("game_started", False):
        emit("error", {"msg": "Game sudah dimulai!"}, to=request.sid)
        return
    
    # Mulai game
    room["game_started"] = True
    
    # Pilih impostor
    impostor_sid = random.choice(players)
    room["impostor_sid"] = impostor_sid
    room["impostor_name"] = room["players"][impostor_sid]
    
    print(f"😈 Impostor: {room['impostor_name']}")
    print(f"🔑 Secret word: {room['word']}")
    
    # Kirim role ke masing-masing pemain
    for sid in players:
        if sid == impostor_sid:
            emit("role", {"text": "IMPOSTOR 😈", "is_impostor": True}, to=sid)
        else:
            emit("role", {"text": room["word"], "is_impostor": False}, to=sid)
    
    # Beri tahu semua game dimulai
    socketio.emit("game_started", {
        "message": "Game dimulai! Clue timer akan segera dimulai..."
    }, room=code)
    
    # Mulai clue timer (pakai background_task)
    print(f"⏰ Starting clue timer for room {code}")
    socketio.start_background_task(clue_timer, code)

@socketio.on("vote")
def handle_vote(data):
    code = data.get("code")
    target = data.get("target")
    
    print(f"🗳️ Vote received - Room: {code}, Target: {target}, Voter: {request.sid}")
    
    if code not in rooms:
        emit("error", {"msg": "Room tidak ditemukan!"}, to=request.sid)
        return
    
    room = rooms[code]
    voter = room["players"].get(request.sid)
    
    if not voter:
        emit("error", {"msg": "Anda tidak terdaftar!"}, to=request.sid)
        return
    
    if target not in room["players"].values():
        emit("error", {"msg": "Target tidak ditemukan!"}, to=request.sid)
        return
    
    # Catat vote
    room["votes"][target] = room["votes"].get(target, 0) + 1
    print(f"📊 Updated votes: {room['votes']}")
    
    socketio.emit("vote_update", room["votes"], room=code)
    emit("vote_confirmed", {"target": target}, to=request.sid)

# ===================== MAIN =====================
if __name__ == "__main__":
    print("🚀 Server starting...")
    print("📍 URL: http://localhost:5000")
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)