import requests
import json
import time
import tkinter as tk
from pathlib import Path
import urllib3
from datetime import datetime
import keyboard

# Suppress only the specific InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
HISTORY_FILE = "league_stats.json"
REFRESH_RATE = 0.1  # 100ms for quick updates
OVERLAY_COLOR = "#00FF00"  # Lime green
DEBUG = True  # Enable debug logging

class LeagueTracker:
    def __init__(self):
        # Initialize state variables
        self.ult_count = 0
        self.current_cs = 0
        self.current_kills = 0
        self.last_mana = None
        self.last_r_press = None
        self.game_started = False
        self.connected_to_game = False
        
        # Load historical data
        self.history = self.load_history()
        self.averages = self.calculate_averages()
        
        # Constants
        self.LUX_ULT_MANA_COST = 100
        self.R_PRESS_WINDOW = 0.5  # 500ms window for R press detection
        
        # Initialize overlay
        self.root = tk.Tk()
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        
        # Create frame with black background
        self.frame = tk.Frame(self.root, bg="black")
        self.frame.pack()
        
        self.label = tk.Label(
            self.frame, 
            text="Waiting for game...", 
            fg=OVERLAY_COLOR, 
            bg="black", 
            font=("Arial", 16),
            justify="left",
        )
        self.label.pack()
        
        # Position the window
        self.position_overlay()
        
        # Setup keyboard hook for R key
        try:
            keyboard.on_press(self.handle_keypress)
            if DEBUG:
                print("Keyboard hook initialized successfully")
        except Exception as e:
            print(f"Error setting up keyboard hook: {e}")

    def handle_keypress(self, event):
        """Handle any key press, but only process 'r' key"""
        try:
            if event.name == 'r':
                self.last_r_press = datetime.now()
                if DEBUG:
                    print(f"\nR key pressed at {self.last_r_press.strftime('%H:%M:%S.%f')[:-3]}")
        except Exception as e:
            print(f"Error in key handler: {e}")

    def position_overlay(self):
        self.root.geometry("+20+20")

    def load_history(self):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"games": []}

    def save_history(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def calculate_averages(self):
        if not self.history["games"]:
            return {"ult": 0, "cs": 0, "kills": 0}
            
        totals = {"ult": 0, "cs": 0, "kills": 0}
        for game in self.history["games"]:
            totals["ult"] += game.get("ult", 0)
            totals["cs"] += game.get("cs", 0)
            totals["kills"] += game.get("kills", 0)
        
        count = len(self.history["games"])
        return {
            "ult": totals["ult"] / count,
            "cs": totals["cs"] / count,
            "kills": totals["kills"] / count
        }

    def reset_stats(self):
        """Reset all stats for a new game"""
        self.ult_count = 0
        self.current_cs = 0
        self.current_kills = 0
        self.last_mana = None
        self.last_r_press = None

    def save_game_stats(self):
        """Save the current game stats to history"""
        if self.game_started:
            self.history["games"].append({
                "timestamp": int(time.time()),
                "ult": self.ult_count,
                "cs": self.current_cs,
                "kills": self.current_kills
            })
            self.save_history()
            if DEBUG:
                print(f"Saved game stats - Ults: {self.ult_count}, CS: {self.current_cs}, Kills: {self.current_kills}")

    def get_api_data(self):
        try:
            response = requests.get(
                "https://127.0.0.1:2999/liveclientdata/allgamedata",
                verify=False,
                timeout=1
            )
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def update_stats(self, data):
        try:
            if DEBUG:
                current_time = datetime.now()
                print(f"\n=== Debug Info {current_time.strftime('%H:%M:%S.%f')[:-3]} ===")

            # Get active player data
            active_player = data["activePlayer"]
            champion_stats = active_player["championStats"]
            current_mana = champion_stats["resourceValue"]
            
            # Check for ult usage by monitoring mana AND R key press
            if self.last_mana is not None:
                mana_change = self.last_mana - current_mana
                
                if DEBUG:
                    print(f"Current Mana: {current_mana:.1f}")
                    print(f"Mana Change: {mana_change:.1f}")
                    if self.last_r_press:
                        time_since_r = (current_time - self.last_r_press).total_seconds()
                        print(f"Time since R press: {time_since_r:.3f}s")
                    else:
                        print("No recent R press")
                
                # Only increment if we see mana change AND recent R press
                if abs(mana_change - self.LUX_ULT_MANA_COST) < 10:
                    time_since_r = float('inf')
                    if self.last_r_press:
                        time_since_r = (current_time - self.last_r_press).total_seconds()
                    
                    if time_since_r < self.R_PRESS_WINDOW:
                        self.ult_count += 1
                        self.last_r_press = None  # Reset the R press detection
                        if DEBUG:
                            print(f"Detected ult use! Count now: {self.ult_count}")
                    else:
                        if DEBUG:
                            print("Mana drop detected but no recent R press")
            
            self.last_mana = current_mana
            
            # Find the active player in allPlayers for score data
            active_player_id = data["activePlayer"]["riotId"]
            active_player_data = next(
                player for player in data["allPlayers"] 
                if player["riotId"] == active_player_id
            )
            
            # Get stats from the scores object
            new_cs = active_player_data["scores"]["creepScore"]
            new_kills = active_player_data["scores"]["kills"]
            
            if DEBUG:
                if new_cs != self.current_cs:
                    print(f"CS changed: {self.current_cs} -> {new_cs}")
                if new_kills != self.current_kills:
                    print(f"Kills changed: {self.current_kills} -> {new_kills}")
            
            self.current_cs = new_cs
            self.current_kills = new_kills
            
            # Update overlay text
            text = (
                f"Ults: {self.ult_count:2d} (Avg: {self.averages['ult']:.1f})\n"
                f"CS:   {self.current_cs:2d} (Avg: {self.averages['cs']:.1f})\n"
                f"Kills: {self.current_kills:2d} (Avg: {self.averages['kills']:.1f})"
            )
            self.label.config(text=text)
            
        except Exception as e:
            print(f"Error in update_stats: {e}")
            if DEBUG:
                import traceback
                traceback.print_exc()

    def update_overlay(self):
        try:
            data = self.get_api_data()
            
            if data:
                if not self.connected_to_game:
                    # We just connected to a game
                    self.connected_to_game = True
                    self.game_started = True
                    self.reset_stats()  # Reset stats for new game
                    if DEBUG:
                        print("New game started - stats reset")
                
                if DEBUG:
                    print("Successfully got API data")
                self.update_stats(data)
                
            else:
                if DEBUG:
                    print("No API data received")
                
                if self.connected_to_game:
                    # We just disconnected from a game - save stats
                    if DEBUG:
                        print(f"Game ended - saving stats...")
                        print(f"Final stats - Ults: {self.ult_count}, CS: {self.current_cs}, Kills: {self.current_kills}")
                    
                    # Save stats to history
                    self.history["games"].append({
                        "timestamp": int(time.time()),
                        "ult": self.ult_count,
                        "cs": self.current_cs,
                        "kills": self.current_kills
                    })
                    self.save_history()
                    
                    # Reset for next game
                    self.reset_stats()
                    self.averages = self.calculate_averages()  # Update averages with new game
                    self.connected_to_game = False
                    self.game_started = False
                    
                    if DEBUG:
                        print("Stats saved to history file")
                        print(f"Current history: {json.dumps(self.history, indent=2)}")
                
                # Update display
                self.label.config(text="Waiting for game...")
                
            # Schedule next update
            self.root.after(int(REFRESH_RATE * 1000), self.update_overlay)
            
        except Exception as e:
            print(f"Overlay update error: {e}")
            if DEBUG:
                import traceback
                traceback.print_exc()
            self.root.after(int(REFRESH_RATE * 1000), self.update_overlay)

    def on_close(self):
        """Handle window closing"""
        if self.connected_to_game:
            self.save_game_stats()
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_overlay()
        self.root.mainloop()

if __name__ == "__main__":
    Path(HISTORY_FILE).touch(exist_ok=True)  # Create file if missing
    tracker = LeagueTracker()
    tracker.run()