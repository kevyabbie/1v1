"""
TEAM MATCHMAKING SYSTEM - PART 10
5v5 Tournament Mode
Host selects killer player and map each round, alternating between teams
"""

import discord
from typing import Optional, Dict, List
from datetime import datetime

# Game Items
SURVIVORS = [
    "Noob", "Guest 1337", "Shedletsky", "Chance", "Two Time",
    "Veeronica", "Elliot", "007n7", "Dusekkar", "Builderman", "Taph"
]

KILLERS = [
    "Noli", "Guest 666", "John Doe", "Slasher", 
    "1x1x1x1", "C00lkidd", "Nosferatu"
]

# Maps
MAPS = [
    "Glasshouses",
    "Pirate bay",
    "Brandonworks",
    "C00l Carnival",
    "Yorick's Resting Place",
    "Planet Voss",
    "Familiar Ruins",
    "Classic Battleground",
    "The Tempest",
    "Work At A Pizza Place"
]

# Map-specific killer recommendations (shown only to attacking team)
MAP_KILLER_RECOMMENDATIONS = {
    "Glasshouses": ["Nosferatu", "Guest 666"],
    "Pirate bay": ["C00lkidd"],
    "Brandonworks": ["Noli"],  # Note: "Brandonworks" killer doesn't exist in KILLERS list
    "C00l Carnival": [],
    "Yorick's Resting Place": [],
    "Planet Voss": ["Slasher"],
    "Familiar Ruins": [],
    "Classic Battleground": ["C00lkidd"],
    "The Tempest": ["C00lkidd"],
    "Work At A Pizza Place": ["1x1x1x1"]
}

# Killer-specific ban recommendations (shown only to defending team)
KILLER_BAN_RECOMMENDATIONS = {
    "Slasher": {
        "solo": ["Elliot", "Builderman", "Two Time", "Veeronica"],
        "combo": [("Dusekkar", "Taph"), ("Chance", "Shedletsky")]
    },
    "Nosferatu": {
        "solo": ["Dusekkar", "Two Time", "Elliot", "007n7", "Guest 1337", "Taph"],
        "combo": []
    },
    "C00lkidd": {
        "solo": ["Guest 1337", "Elliot", "Builderman", "Chance", "Two Time"],
        "combo": [("Dusekkar", "Taph")]
    },
    "John Doe": {
        "solo": ["Elliot", "Two Time", "Veeronica", "Chance", "Shedletsky"],
        "combo": [("Dusekkar", "Taph")]
    },
    "Guest 666": {
        "solo": ["Guest 1337", "Shedletsky", "Two Time", "Chance"],
        "combo": [("Dusekkar", "Taph"), ("Elliot", "007n7")]
    },
    "1x1x1x1": {
        "solo": ["Guest 1337", "Builderman", "Veeronica", "Two Time"],
        "combo": [("Elliot", "Dusekkar"), ("Shedletsky", "Chance")]
    },
    "Noli": {
        "solo": ["Guest 1337", "Elliot", "Taph", "Shedletsky", "Dusekkar", "Builderman", "007n7"],
        "combo": []
    }
}

# 5v5 Tournament Constants
TOURNAMENT_ROUNDS = 10
TOURNAMENT_WIN_POINTS = 10  # Points for winning team
TOURNAMENT_LOSS_POINTS = -10  # Points for losing team
MAX_SURVIVOR_BANS = 2  # 2 bans per defending team


class Tournament5v5Match:
    """Represents a 5v5 tournament match"""
    def __init__(self, team_a: List[discord.Member], team_b: List[discord.Member], 
                 channel: discord.TextChannel):
        self.team_a = team_a  # List of 5 members
        self.team_b = team_b
        self.team_a_host = team_a[0]  # Host is always first member
        self.team_b_host = team_b[0]
        self.channel = channel
        self.thread: Optional[discord.Thread] = None
        
        # Match state
        self.current_round = 1
        self.current_phase = "map_select"  # "map_select", "killer_select", "ban", "pick", "results"
        self.attacking_team = "A"  # Team that has the killer this round
        
        # Round tracking
        self.selected_map: Optional[str] = None
        self.selected_killer_player_index: Optional[int] = None  # Which player (0-4) is killer
        self.selected_killer_character: Optional[str] = None  # Which killer character
        self.banned_survivors: List[str] = []  # Survivors banned by defending team
        
        # Survivor picks (defending team) - player_index -> character
        self.round_survivor_picks: Dict[int, str] = {}
        
        # Match scoring
        self.team_a_score = 0
        self.team_b_score = 0
        self.rounds_completed = 0
        self.team_a_claimed: Optional[str] = None
        self.team_b_claimed: Optional[str] = None
        self.match_complete = False
        
        # Status tracking
        self.status_message: Optional[discord.Message] = None
        self.history: List[Dict] = []  # Store round history
    
    def get_attacking_team(self) -> str:
        """Get which team is attacking (has killer) this round"""
        # Alternates: Round 1=A, 2=B, 3=A, 4=B, etc.
        return "A" if self.current_round % 2 == 1 else "B"
    
    def get_defending_team(self) -> str:
        """Get which team is defending (all survivors) this round"""
        return "B" if self.attacking_team == "A" else "A"
    
    def get_attacking_host(self) -> discord.Member:
        """Get host of attacking team"""
        return self.team_a_host if self.attacking_team == "A" else self.team_b_host
    
    def get_defending_host(self) -> discord.Member:
        """Get host of defending team"""
        return self.team_b_host if self.attacking_team == "A" else self.team_a_host
    
    def get_team_members(self, team: str) -> List[discord.Member]:
        """Get members of a team"""
        return self.team_a if team == "A" else self.team_b
    
    def get_team_host(self, team: str) -> discord.Member:
        """Get host of a team"""
        return self.team_a_host if team == "A" else self.team_b_host
    
    def is_team_host(self, user: discord.Member) -> Optional[str]:
        """Check if user is a team host, return team letter or None"""
        if user.id == self.team_a_host.id:
            return "A"
        elif user.id == self.team_b_host.id:
            return "B"
        return None
    
    def get_user_team(self, user: discord.Member) -> Optional[str]:
        """Get which team a user is on"""
        if user.id in [m.id for m in self.team_a]:
            return "A"
        elif user.id in [m.id for m in self.team_b]:
            return "B"
        return None
    
    def reset_round_state(self):
        """Reset state for next round"""
        self.selected_map = None
        self.selected_killer_player_index = None
        self.selected_killer_character = None
        self.banned_survivors.clear()
        self.round_survivor_picks.clear()
        self.current_phase = "map_select"
        self.attacking_team = self.get_attacking_team()
    
    def get_available_survivors_for_pick(self) -> List[str]:
        """Get survivors available for defending team to pick"""
        available = []
        for survivor in SURVIVORS:
            # Not banned and not already picked
            if survivor not in self.banned_survivors and survivor not in self.round_survivor_picks.values():
                available.append(survivor)
        return available
    
    def is_picks_complete(self) -> bool:
        """Check if all 5 defending players have picked survivors"""
        return len(self.round_survivor_picks) >= 5
    
    def save_round_history(self):
        """Save completed round to history"""
        defending_team = self.get_defending_team()
        defending_members = self.get_team_members(defending_team)
        
        survivor_picks_formatted = []
        for i in range(5):
            player = defending_members[i]
            survivor = self.round_survivor_picks.get(i, "None")
            survivor_picks_formatted.append(f"{player.display_name}: {survivor}")
        
        killer_player = self.get_team_members(self.attacking_team)[self.selected_killer_player_index]
        
        round_data = {
            "round": self.rounds_completed,
            "map": self.selected_map,
            "attacking_team": self.attacking_team,
            "killer_player": killer_player.display_name,
            "killer_character": self.selected_killer_character,
            "bans": list(self.banned_survivors),
            "defender_picks": survivor_picks_formatted,
            "winner": "A" if self.team_a_claimed == "win" else "B"
        }
        
        self.history.append(round_data)
