"""
TEAM MATCHMAKING SYSTEM - PART 2
Team Match Classes
Defines team match structure, rounds, and game constants
"""

import discord
from typing import List, Dict, Optional
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

# Team Points
TEAM_POINTS = {
    "2v2": {"win": 8, "loss": -7},
    "3v3": {"win": 7, "loss": -7},
    "4v4": {"win": 6, "loss": -6}
}

# Ban Limits
TEAM_BAN_LIMITS = {
    "2v2": 1,   # 1 ban per team
    "3v3": 0,   # No bans
    "4v4": 0    # No bans
}


class TeamMatch:
    """Represents a team match (2v2, 3v3, or 4v4)"""
    def __init__(self, team_a: List[discord.Member], team_b: List[discord.Member], 
                 mode: str, channel: discord.TextChannel):
        self.team_a = team_a
        self.team_b = team_b
        self.mode = mode  # "2v2", "3v3", or "4v4"
        self.channel = channel
        self.thread: Optional[discord.Thread] = None
        
        # Match state
        self.current_phase = "ban" if TEAM_BAN_LIMITS[mode] > 0 else "pick"
        self.current_round = 1
        
        # Bans (only for 2v2)
        self.team_a_bans: List[str] = []
        self.team_b_bans: List[str] = []
        
        # Picks (player_index -> character)
        self.team_a_picks: Dict[int, str] = {}
        self.team_b_picks: Dict[int, str] = {}
        
        # Match scoring
        self.team_a_score = 0
        self.team_b_score = 0
        self.rounds_completed = 0
        self.team_a_claimed: Optional[str] = None
        self.team_b_claimed: Optional[str] = None
        self.in_tiebreaker = False
        
        # Total rounds for mode
        self.total_rounds = {
            "2v2": 4,  # Each player gets 2 rounds
            "3v3": 6,  # Each player gets 2 rounds  
            "4v4": 8   # Each player gets 2 rounds
        }[mode]
        
        self.status_message: Optional[discord.Message] = None
    
    def get_ban_limit(self) -> int:
        """Get ban limit for this mode"""
        return TEAM_BAN_LIMITS[self.mode]
    
    def can_ban(self, team: str) -> bool:
        """Check if team can still ban"""
        bans = self.team_a_bans if team == "A" else self.team_b_bans
        return len(bans) < self.get_ban_limit()
    
    def add_ban(self, team: str, character: str):
        """Add a ban"""
        if team == "A":
            self.team_a_bans.append(character)
        else:
            self.team_b_bans.append(character)
    
    def add_pick(self, team: str, player_index: int, character: str):
        """Add a pick"""
        if team == "A":
            self.team_a_picks[player_index] = character
        else:
            self.team_b_picks[player_index] = character
    
    def get_round_pattern(self, round_num: int) -> Dict:
        """Get killer/survivor pattern for a round"""
        if self.mode == "2v2":
            # 4 rounds: alternating killer between teams
            # Round 1: A killer, B survivors
            # Round 2: B killer, A survivors
            # Round 3: A killer, B survivors (2nd player)
            # Round 4: B killer, A survivors (2nd player)
            patterns = [
                {"team_a": ["killer", "survivor"], "team_b": ["survivor", "survivor"]},
                {"team_a": ["survivor", "survivor"], "team_b": ["killer", "survivor"]},
                {"team_a": ["survivor", "killer"], "team_b": ["survivor", "survivor"]},
                {"team_a": ["survivor", "survivor"], "team_b": ["survivor", "killer"]}
            ]
            return patterns[round_num - 1]
        
        elif self.mode == "3v3":
            # 6 rounds: each player gets killer once
            patterns = [
                {"team_a": ["killer", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor"], "team_b": ["killer", "survivor", "survivor"]},
                {"team_a": ["survivor", "killer", "survivor"], "team_b": ["survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor"], "team_b": ["survivor", "killer", "survivor"]},
                {"team_a": ["survivor", "survivor", "killer"], "team_b": ["survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "killer"]}
            ]
            return patterns[round_num - 1]
        
        else:  # 4v4
            # 8 rounds: each player gets killer once
            patterns = [
                {"team_a": ["killer", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["killer", "survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "killer", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "killer", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "killer", "survivor"], "team_b": ["survivor", "survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "killer", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor", "killer"], "team_b": ["survivor", "survivor", "survivor", "survivor"]},
                {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "killer"]}
            ]
            return patterns[round_num - 1]
    
    def is_team_host(self, user: discord.Member) -> Optional[str]:
        """Check if user is a team host"""
        if user.id == self.team_a[0].id:
            return "A"
        elif user.id == self.team_b[0].id:
            return "B"
        return None
    
    def get_team_host(self, team: str) -> discord.Member:
        """Get team host"""
        return self.team_a[0] if team == "A" else self.team_b[0]
    
    def get_user_team(self, user: discord.Member) -> Optional[str]:
        """Get which team user is on"""
        if user.id in [m.id for m in self.team_a]:
            return "A"
        elif user.id in [m.id for m in self.team_b]:
            return "B"
        return None
    
    def get_user_team_by_id(self, user_id: int) -> Optional[str]:
        """Get team by user ID"""
        if user_id in [m.id for m in self.team_a]:
            return "A"
        elif user_id in [m.id for m in self.team_b]:
            return "B"
        return None
    
    def get_team_members(self, team: str) -> List[discord.Member]:
        """Get team members"""
        return self.team_a if team == "A" else self.team_b
    
    def is_pick_phase_complete(self) -> bool:
        """Check if all picks are done for current round"""
        pattern = self.get_round_pattern(self.current_round)
        
        # Check team A
        for i, role in enumerate(pattern["team_a"]):
            if i not in self.team_a_picks:
                return False
        
        # Check team B
        for i, role in enumerate(pattern["team_b"]):
            if i not in self.team_b_picks:
                return False
        
        return True
    
    def reset_picks_for_next_round(self):
        """Reset picks for next round"""
        self.team_a_picks.clear()
        self.team_b_picks.clear()
    
    def check_for_tiebreaker(self) -> bool:
        """Check if tiebreaker is needed"""
        return self.team_a_score == self.team_b_score
    
    def get_available_killers(self) -> List[str]:
        """Get available killers (not banned)"""
        banned = self.team_a_bans + self.team_b_bans
        return [k for k in KILLERS if k not in banned]
    
    def get_available_survivors(self, team: str) -> List[str]:
        """Get available survivors for a team"""
        banned = self.team_a_bans + self.team_b_bans
        picks = self.team_a_picks if team == "A" else self.team_b_picks
        picked = list(picks.values())
        
        return [s for s in SURVIVORS if s not in banned and s not in picked]
