import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import uuid
from typing import Optional, Dict, List, Any

# Load environment variables
load_dotenv()

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env")
        
        self.supabase: Client = create_client(url, key)
    
    # ==================== ROOM OPERATIONS ====================
    
    def create_room(self, code: str, host_id: str, host_name: str, word: str) -> Dict:
        """Membuat room baru"""
        room_data = {
            "code": code,
            "host_id": host_id,
            "host_name": host_name,
            "word": word,
            "current_clue_giver_id": host_id,
            "current_clue_giver_name": host_name,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "messages": [],
            "votes": {},
            "voters": []
        }
        
        result = self.supabase.table("rooms").insert(room_data).execute()
        return result.data[0] if result.data else None
    
    def get_room(self, code: str) -> Optional[Dict]:
        """Mendapatkan room berdasarkan kode"""
        result = self.supabase.table("rooms").select("*").eq("code", code).execute()
        return result.data[0] if result.data else None
    
    def update_room(self, code: str, updates: Dict) -> Optional[Dict]:
        """Update room data"""
        # Auto-update last_activity
        updates["last_activity"] = datetime.now().isoformat()
        
        result = self.supabase.table("rooms").update(updates).eq("code", code).execute()
        return result.data[0] if result.data else None
    
    def delete_room(self, code: str) -> bool:
        """Menghapus room"""
        result = self.supabase.table("rooms").delete().eq("code", code).execute()
        return len(result.data) > 0
    
    def cleanup_old_rooms(self) -> int:
        """Bersihkan room yang tidak aktif > 2 jam"""
        cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        result = self.supabase.table("rooms").delete().lt("last_activity", cutoff).execute()
        return len(result.data)
    
    # ==================== PLAYER OPERATIONS ====================
    
    def add_player(self, player_id: str, room_code: str, name: str) -> Dict:
        """Menambahkan player ke room"""
        player_data = {
            "id": player_id,
            "room_code": room_code,
            "name": name,
            "joined_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        result = self.supabase.table("players").insert(player_data).execute()
        return result.data[0] if result.data else None
    
    def get_players(self, room_code: str) -> List[Dict]:
        """Mendapatkan semua player dalam room"""
        result = self.supabase.table("players") \
            .select("*") \
            .eq("room_code", room_code) \
            .eq("is_active", True) \
            .order("joined_at") \
            .execute()
        return result.data
    
    def remove_player(self, player_id: str, room_code: str) -> bool:
        """Menghapus player (soft delete dengan is_active = false)"""
        result = self.supabase.table("players") \
            .update({"is_active": False}) \
            .eq("id", player_id) \
            .eq("room_code", room_code) \
            .execute()
        return len(result.data) > 0
    
    def update_player_name(self, player_id: str, room_code: str, new_name: str) -> bool:
        """Update nama player"""
        result = self.supabase.table("players") \
            .update({"name": new_name}) \
            .eq("id", player_id) \
            .eq("room_code", room_code) \
            .execute()
        return len(result.data) > 0
    
    def count_active_players(self, room_code: str) -> int:
        """Menghitung jumlah player aktif dalam room"""
        result = self.supabase.table("players") \
            .select("*", count="exact") \
            .eq("room_code", room_code) \
            .eq("is_active", True) \
            .execute()
        return result.count if hasattr(result, 'count') else 0
    
    # ==================== GAME OPERATIONS ====================
    
    def start_game(self, room_code: str, impostor_id: str, impostor_name: str) -> Dict:
        """Memulai game"""
        updates = {
            "game_started": True,
            "impostor_id": impostor_id,
            "impostor_name": impostor_name,
            "clue_time": 20,
            "voting_time": 0
        }
        return self.update_room(room_code, updates)
    
    def start_voting(self, room_code: str) -> Dict:
        """Memulai fase voting"""
        updates = {
            "voting_time": 40,
            "clue_time": 0,
            "votes": {},
            "voters": []
        }
        return self.update_room(room_code, updates)
    
    def add_vote(self, room_code: str, voter_id: str, target_id: str) -> Dict:
        """Menambahkan vote"""
        # Get current room data
        room = self.get_room(room_code)
        if not room:
            return None
        
        # Update votes
        votes = room.get("votes", {})
        voters = room.get("voters", [])
        
        votes[voter_id] = target_id
        if voter_id not in voters:
            voters.append(voter_id)
        
        updates = {
            "votes": votes,
            "voters": voters
        }
        
        return self.update_room(room_code, updates)
    
    def set_clue_giver(self, room_code: str, clue_giver_id: str, clue_giver_name: str) -> Dict:
        """Set pemberi clue"""
        updates = {
            "current_clue_giver_id": clue_giver_id,
            "current_clue_giver_name": clue_giver_name
        }
        return self.update_room(room_code, updates)
    
    def decrement_timers(self, room_code: str) -> Dict:
        """Mengurangi timer (clue_time dan voting_time)"""
        room = self.get_room(room_code)
        if not room:
            return None
        
        updates = {}
        
        if room.get("game_started") and room.get("clue_time", 0) > 0:
            updates["clue_time"] = room["clue_time"] - 1
        
        if room.get("voting_time", 0) > 0:
            updates["voting_time"] = room["voting_time"] - 1
        
        if updates:
            return self.update_room(room_code, updates)
        
        return room
    
    # ==================== CHAT OPERATIONS ====================
    
    def add_message(self, room_code: str, name: str, message: str) -> Dict:
        """Menambahkan pesan chat"""
        room = self.get_room(room_code)
        if not room:
            return None
        
        messages = room.get("messages", [])
        
        new_message = {
            "name": name,
            "message": message,
            "time": datetime.now().strftime("%H:%M")
        }
        
        messages.append(new_message)
        
        # Batasi 50 pesan terakhir
        if len(messages) > 50:
            messages = messages[-50:]
        
        return self.update_room(room_code, {"messages": messages})
    
    # ==================== RESULT OPERATIONS ====================
    
    def save_result(self, room_code: str, result_data: Dict) -> Dict:
        """Menyimpan hasil voting"""
        return self.update_room(room_code, {"last_result": result_data})
    
    def reset_game(self, room_code: str, new_word: str) -> Dict:
        """Reset game untuk ronde baru"""
        updates = {
            "word": new_word,
            "impostor_id": None,
            "impostor_name": None,
            "votes": {},
            "voters": [],
            "game_started": False,
            "clue_time": 0,
            "voting_time": 0,
            "last_result": None
        }
        return self.update_room(room_code, updates)
    
    # ==================== UTILITY ====================
    
    def room_exists(self, code: str) -> bool:
        """Cek apakah room exists"""
        result = self.supabase.table("rooms").select("code").eq("code", code).execute()
        return len(result.data) > 0
    
    def is_name_available(self, room_code: str, name: str) -> bool:
        """Cek apakah nama tersedia dalam room"""
        result = self.supabase.table("players") \
            .select("name") \
            .eq("room_code", room_code) \
            .eq("name", name) \
            .eq("is_active", True) \
            .execute()
        return len(result.data) == 0
    
    def get_host(self, room_code: str) -> Optional[Dict]:
        """Mendapatkan data host"""
        room = self.get_room(room_code)
        if not room:
            return None
        
        return {
            "id": room["host_id"],
            "name": room["host_name"]
        }

# Singleton instance
supabase_client = SupabaseClient()