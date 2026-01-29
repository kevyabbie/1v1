"""
TEAM MATCHMAKING SYSTEM - PART 7
Multi-Mode Stats System
Separate stats and leaderboards for 1v1, 2v2, 3v3, 4v4
Enhanced with visual banner leaderboards
"""

import discord
import json
import os
from typing import Dict, Optional
import requests
from io import BytesIO
from PIL import Image
import colorsys


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
    """Create leaderboard embed for a mode (LEGACY - simple version)"""
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


async def extract_dominant_color_from_banner(banner_url: str) -> discord.Color:
    """Extract dominant color from banner image for embed theming"""
    try:
        response = requests.get(banner_url, timeout=5)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            
            # Resize for faster processing
            img = img.resize((150, 150))
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Get pixels
            pixels = list(img.getdata())
            
            # Find most common color (excluding very dark/light)
            color_count = {}
            for pixel in pixels:
                r, g, b = pixel
                # Skip very dark or very light pixels
                brightness = sum(pixel) / 3
                if 30 < brightness < 225:
                    # Round to reduce variations
                    r = (r // 10) * 10
                    g = (g // 10) * 10
                    b = (b // 10) * 10
                    color = (r, g, b)
                    color_count[color] = color_count.get(color, 0) + 1
            
            if color_count:
                # Get most common color
                dominant = max(color_count, key=color_count.get)
                
                # Increase saturation for better visual
                h, s, v = colorsys.rgb_to_hsv(dominant[0]/255, dominant[1]/255, dominant[2]/255)
                s = min(s * 1.3, 1.0)  # Boost saturation
                v = max(min(v * 1.2, 1.0), 0.4)  # Adjust brightness
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                
                return discord.Color.from_rgb(int(r*255), int(g*255), int(b*255))
    except Exception as e:
        print(f"Error extracting color from banner: {e}")
    
    # Default to gold if extraction fails
    return discord.Color.gold()


async def create_visual_leaderboard_embed(mode: str, leaderboard: list, 
                                         profile_system, guild: discord.Guild) -> discord.Embed:
    """
    Create enhanced leaderboard embed with #1 player's banner and profile
    
    Layout:
    - Banner image at top (if #1 has one)
    - Profile picture thumbnail
    - Player name, ELO/Points, W/L, and bio
    - Top 10 rankings below
    - Color theme extracted from banner
    """
    
    if not leaderboard:
        embed = discord.Embed(
            title=f"🏆 {mode.upper()} Leaderboard - Top 10",
            description="No players yet!",
            color=discord.Color.gold()
        )
        return embed
    
    # Get #1 player
    top_player_stats = leaderboard[0]
    top_player_profile = profile_system.profiles.get(top_player_stats.user_id)
    
    # Try to get Discord member for avatar
    top_member = None
    try:
        top_member = await guild.fetch_member(top_player_stats.user_id)
    except:
        pass
    
    # Extract color from banner or use default
    embed_color = discord.Color.gold()
    if top_player_profile and top_player_profile.banner_url:
        embed_color = await extract_dominant_color_from_banner(top_player_profile.banner_url)
    
    # Create embed
    embed = discord.Embed(
        title=f"🏆 {mode.upper()} Leaderboard - Top 10",
        color=embed_color
    )
    
    # Set #1 player's banner as main image (if they have one)
    if top_player_profile and top_player_profile.banner_url:
        embed.set_image(url=top_player_profile.banner_url)
    
    # Set #1 player's avatar as thumbnail
    if top_member and top_member.avatar:
        embed.set_thumbnail(url=top_member.avatar.url)
    
    # Create #1 player showcase section
    top_player_showcase = f"👑 **{top_player_stats.username}**\n\n"
    
    # Stats line: Points, Wins, Losses
    winrate = 0
    total_games = top_player_stats.wins + top_player_stats.losses
    if total_games > 0:
        winrate = (top_player_stats.wins / total_games) * 100
    
    top_player_showcase += f"**ELO:** {top_player_stats.points} 🌟 "
    top_player_showcase += f"**WIN:** {top_player_stats.wins} ✅ "
    top_player_showcase += f"**LOSE:** {top_player_stats.losses} ❌\n"
    top_player_showcase += f"**Win Rate:** {winrate:.1f}%\n\n"
    
    # Add bio if exists
    if top_player_profile and top_player_profile.bio:
        bio_text = top_player_profile.bio
        if len(bio_text) > 150:
            bio_text = bio_text[:147] + "..."
        top_player_showcase += f"*\"{bio_text}\"*\n"
    
    embed.add_field(
        name="━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        value=top_player_showcase,
        inline=False
    )
    
    # Add separator
    embed.add_field(
        name="━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        value="** **",  # Empty space
        inline=False
    )
    
    # Top 10 Rankings
    rankings_text = ""
    
    for i, stats in enumerate(leaderboard[:10], 1):
        total = stats.wins + stats.losses
        wr = 0
        if total > 0:
            wr = (stats.wins / total) * 100
        
        # Medal emojis for top 3
        if i == 1:
            medal = "1️⃣"
        elif i == 2:
            medal = "2️⃣"
        elif i == 3:
            medal = "3️⃣"
        else:
            medal = f"`{i}.`"
        
        # Compact format
        rankings_text += f"{medal} **{stats.username}** - "
        rankings_text += f"{stats.points}pts • "
        rankings_text += f"{stats.wins}W/{stats.losses}L • "
        rankings_text += f"{wr:.0f}% WR\n"
    
    embed.add_field(
        name="📊 Full Rank",
        value=rankings_text if rankings_text else "No rankings yet",
        inline=False
    )
    
    # Footer
    embed.set_footer(
        text=f"🎮 Total Players: {len(leaderboard)} | Keep Competitive!!!!",
        icon_url=top_member.avatar.url if (top_member and top_member.avatar) else None
    )
    
    return embed
