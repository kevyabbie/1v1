"""
TEAM MATCHMAKING SYSTEM - PART 10 (FIXED V2)
5v5 Tournament Mode with Score Tracking
Host selects map, killer player each round, alternating between teams
Stores round-by-round scores for detailed breakdown
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
    "Brandonworks": ["Noli"],
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
MAX_SURVIVOR_BANS = 2  # 2 bans per defending team per round


class Tournament5v5Match:
    """Represents a 5v5 tournament match"""
    def __init__(self, team_a: List[discord.Member], team_b: List[discord.Member], 
                 team_a_name: str, team_b_name: str, channel: discord.TextChannel):
        self.team_a = team_a  # List of 5 members (index 0 is always host)
        self.team_b = team_b
        self.team_a_name = team_a_name  # Party name
        self.team_b_name = team_b_name  # Party name
        self.team_a_host = team_a[0]  # Host is always first member (player 1)
        self.team_b_host = team_b[0]
        self.channel = channel
        self.thread: Optional[discord.Thread] = None
        
        # Match state
        self.current_round = 1
        self.current_phase = "map_select"  # "map_select", "killer_select", "ban", "pick", "results"
        
        # Round tracking
        self.selected_map: Optional[str] = None
        self.selected_killer_player_index: Optional[int] = None  # Which player (0-4) is killer
        self.selected_killer_character: Optional[str] = None  # Which killer character
        self.banned_survivors: List[str] = []  # Survivors banned by defending team (max 2)
        
        # Survivor picks (defending team) - player_index -> character
        self.round_survivor_picks: Dict[int, str] = {}
        
        # Match scoring
        self.team_a_score = 0  # Number of rounds won
        self.team_b_score = 0  # Number of rounds won
        self.rounds_completed = 0
        self.team_a_claimed: Optional[int] = None  # Changed to store score (0-5)
        self.team_b_claimed: Optional[int] = None  # Changed to store score (0-5)
        self.match_complete = False
        
        # Status tracking
        self.status_message: Optional[discord.Message] = None
        self.history: List[Dict] = []  # Store round history with scores
    
    def get_attacking_team(self) -> str:
        """Get which team is attacking (has killer) this round"""
        # Alternates: Round 1=A, 2=B, 3=A, 4=B, etc.
        return "A" if self.current_round % 2 == 1 else "B"
    
    def get_defending_team(self) -> str:
        """Get which team is defending (all survivors) this round"""
        return "B" if self.get_attacking_team() == "A" else "A"
    
    def get_attacking_host(self) -> discord.Member:
        """Get host of attacking team"""
        return self.team_a_host if self.get_attacking_team() == "A" else self.team_b_host
    
    def get_defending_host(self) -> discord.Member:
        """Get host of defending team"""
        return self.team_b_host if self.get_attacking_team() == "A" else self.team_a_host
    
    def get_team_members(self, team: str) -> List[discord.Member]:
        """Get members of a team"""
        return self.team_a if team == "A" else self.team_b
    
    def get_team_name(self, team: str) -> str:
        """Get party name of a team"""
        return self.team_a_name if team == "A" else self.team_b_name
    
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
    
    def get_user_index_in_team(self, user: discord.Member) -> Optional[int]:
        """Get player's index (0-4) in their team"""
        team = self.get_user_team(user)
        if not team:
            return None
        
        members = self.get_team_members(team)
        for i, member in enumerate(members):
            if member.id == user.id:
                return i
        return None
    
    def reset_round_state(self):
        """Reset state for next round"""
        self.selected_map = None
        self.selected_killer_player_index = None
        self.selected_killer_character = None
        self.banned_survivors.clear()
        self.round_survivor_picks.clear()
        self.current_phase = "map_select"
    
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
    
    def is_bans_complete(self) -> bool:
        """Check if defending host has completed bans (max 2)"""
        return len(self.banned_survivors) >= MAX_SURVIVOR_BANS
    
    def save_round_history(self):
        """Save completed round to history WITH SCORES"""
        defending_team = self.get_defending_team()
        defending_members = self.get_team_members(defending_team)
        
        survivor_picks_formatted = []
        for i in range(5):
            player = defending_members[i]
            survivor = self.round_survivor_picks.get(i, "None")
            survivor_picks_formatted.append(f"{player.display_name}: {survivor}")
        
        attacking_team = self.get_attacking_team()
        killer_player = self.get_team_members(attacking_team)[self.selected_killer_player_index]
        
        # Determine winner
        if self.team_a_claimed > self.team_b_claimed:
            winner = self.team_a_name
        elif self.team_b_claimed > self.team_a_claimed:
            winner = self.team_b_name
        else:
            winner = "Tie"
        
        round_data = {
            "round": self.rounds_completed,
            "map": self.selected_map,
            "attacking_team": self.get_team_name(attacking_team),
            "defending_team": self.get_team_name(defending_team),
            "killer_player": killer_player.display_name,
            "killer_character": self.selected_killer_character,
            "bans": list(self.banned_survivors),
            "defender_picks": survivor_picks_formatted,
            "team_a_points": self.team_a_claimed,  # NEW: Store round scores
            "team_b_points": self.team_b_claimed,  # NEW: Store round scores
            "winner": winner
        }
        
        self.history.append(round_data)
