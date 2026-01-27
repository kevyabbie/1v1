"""
TEAM MATCHMAKING SYSTEM - PART 7
Multi-Mode Stats System
Separate stats and leaderboards for 1v1, 2v2, 3v3, 4v4
"""

import discord
import json
import os
from typing import Dict, Optional


class ModeStats:
    """Stats for a specific game mode"""
    def __init__(self, user_id: int, username: str, mode: str):
        self.user_id = user_id
        self.username = username
        self.mode = mode  # "1v1", "2v2", "3v3", "4v4"
        self.points = 0
        self.wins = 0
        self.losses = 0
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'mode': self.mode,
            'points': self.points,
            'wins': self.wins,
            'losses': self.losses
        }
    
    @classmethod
    def from_dict(cls, data):
        stats = cls(data['user_id'], data['username'], data['mode'])
        stats.points = data['points']
        stats.wins = data['wins']
        stats.losses = data['losses']
        return stats


class MultiModeStatsSystem:
    """Manages stats across all game modes"""
    def __init__(self):
        # Structure: mode -> user_id -> ModeStats
        self.stats: Dict[str, Dict[int, ModeStats]] = {
            "1v1": {},
            "2v2": {},
            "3v3": {},
            "4v4": {},
            "5v5": {}
        }
        self.stats_file = "multi_mode_stats.json"
        self.load_stats()
    
    def load_stats(self):
        """Load stats from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    for mode, users in data.items():
                        if mode not in self.stats:
                            continue
                        for user_id_str, stats_dict in users.items():
                            user_id = int(user_id_str)
                            self.stats[mode][user_id] = ModeStats.from_dict(stats_dict)
                
                # Auto-fix negative points
                fixed_count = 0
                for mode in self.stats:
                    for stats in self.stats[mode].values():
                        if stats.points < 0:
                            print(f"Auto-fixing negative points for {stats.username} in {mode}: {stats.points} → 0")
                            stats.points = 0
                            fixed_count += 1
                
                if fixed_count > 0:
                    print(f"✅ Auto-fixed {fixed_count} player(s) with negative points")
                    self.save_stats()
                    
            except Exception as e:
                print(f"Error loading multi-mode stats: {e}")
    
    def save_stats(self):
        """Save stats to file"""
        try:
            data = {}
            for mode, users in self.stats.items():
                data[mode] = {str(uid): stats.to_dict() for uid, stats in users.items()}
            
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving multi-mode stats: {e}")
    
    def get_or_create_stats(self, user: discord.Member, mode: str) -> ModeStats:
        """Get or create stats for a user in a specific mode"""
        if mode not in self.stats:
            mode = "1v1"  # Default
        
        if user.id not in self.stats[mode]:
            self.stats[mode][user.id] = ModeStats(user.id, user.name, mode)
        
        return self.stats[mode][user.id]
    
    def get_stats(self, user: discord.Member, mode: str) -> Optional[ModeStats]:
        """Get stats for a user in a specific mode (returns None if not found)"""
        if mode not in self.stats:
            return None
        return self.stats[mode].get(user.id)
    
    def get_leaderboard(self, mode: str, limit: int = 10) -> list:
        """Get top players for a mode"""
        if mode not in self.stats:
            return []
        
        sorted_stats = sorted(
            self.stats[mode].values(),
            key=lambda s: s.points,
            reverse=True
        )
        
        return sorted_stats[:limit]
    
    def get_all_modes_summary(self, user: discord.Member) -> Dict[str, ModeStats]:
        """Get stats summary across all modes for a user"""
        summary = {}
        for mode in self.stats:
            if user.id in self.stats[mode]:
                summary[mode] = self.stats[mode][user.id]
        return summary


def create_stats_embed(user: discord.Member, stats: ModeStats) -> discord.Embed:
    """Create stats embed for a specific mode"""
    embed = discord.Embed(
        title=f"📊 {stats.mode.upper()} Stats for {user.display_name}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Points", value=str(stats.points), inline=True)
    embed.add_field(name="Wins", value=str(stats.wins), inline=True)
    embed.add_field(name="Losses", value=str(stats.losses), inline=True)
    
    if stats.wins + stats.losses > 0:
        winrate = (stats.wins / (stats.wins + stats.losses)) * 100
        embed.add_field(name="Win Rate", value=f"{winrate:.1f}%", inline=True)
    
    return embed


def create_multi_mode_stats_embed(user: discord.Member, multi_stats: MultiModeStatsSystem) -> discord.Embed:
    """Create comprehensive stats embed showing all modes"""
    embed = discord.Embed(
        title=f"📊 All Stats for {user.display_name}",
        color=discord.Color.blue()
    )
    
    summary = multi_stats.get_all_modes_summary(user)
    
    for mode in ["1v1", "2v2", "3v3", "4v4", "5v5"]:
        if mode in summary:
            stats = summary[mode]
            winrate = 0
            if stats.wins + stats.losses > 0:
                winrate = (stats.wins / (stats.wins + stats.losses)) * 100
            
            value = (f"**Points:** {stats.points}\n"
                    f"**W/L:** {stats.wins}/{stats.losses}\n"
                    f"**Win Rate:** {winrate:.1f}%")
        else:
            value = "No games played"
        
        embed.add_field(
            name=f"{mode.upper()}",
            value=value,
            inline=True
        )
    
    return embed


def create_leaderboard_embed(mode: str, leaderboard: list) -> discord.Embed:
    """Create leaderboard embed for a mode"""
    embed = discord.Embed(
        title=f"🏆 {mode.upper()} Leaderboard - Top 10",
        color=discord.Color.gold()
    )
    
    if not leaderboard:
        embed.description = "No players yet!"
        return embed
    
    for i, stats in enumerate(leaderboard, 1):
        winrate = 0
        if stats.wins + stats.losses > 0:
            winrate = (stats.wins / (stats.wins + stats.losses)) * 100
        
        embed.add_field(
            name=f"{i}. {stats.username}",
            value=f"**Points:** {stats.points} | **W/L:** {stats.wins}/{stats.losses} | **WR:** {winrate:.1f}%",
            inline=False
        )
    
    return embed
