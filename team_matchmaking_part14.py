"""
TEAM MATCHMAKING SYSTEM - PART 14
Player Profile & Banner System
Customizable profiles with banners, bio, mains, and detailed stats
"""

import discord
from discord import app_commands
from typing import Optional, Dict
import json
import os
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap


class PlayerProfile:
    """Enhanced player profile with customization"""
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        
        # Customizable profile fields
        self.banner_url: Optional[str] = None  # Discord CDN link
        self.bio: str = ""
        self.main_survivor: Optional[str] = None
        self.main_killer: Optional[str] = None
        
        # Detailed stats
        self.playtime_hours: int = 0
        self.killer_wins: int = 0
        self.survivor_wins: int = 0
        
        # Timestamps
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'banner_url': self.banner_url,
            'bio': self.bio,
            'main_survivor': self.main_survivor,
            'main_killer': self.main_killer,
            'playtime_hours': self.playtime_hours,
            'killer_wins': self.killer_wins,
            'survivor_wins': self.survivor_wins,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        profile = cls(data['user_id'], data['username'])
        profile.banner_url = data.get('banner_url')
        profile.bio = data.get('bio', '')
        profile.main_survivor = data.get('main_survivor')
        profile.main_killer = data.get('main_killer')
        profile.playtime_hours = data.get('playtime_hours', 0)
        profile.killer_wins = data.get('killer_wins', 0)
        profile.survivor_wins = data.get('survivor_wins', 0)
        
        if 'created_at' in data:
            profile.created_at = datetime.fromisoformat(data['created_at'])
        if 'last_updated' in data:
            profile.last_updated = datetime.fromisoformat(data['last_updated'])
        
        return profile


class ProfileSystem:
    """Manages player profiles"""
    def __init__(self):
        self.profiles: Dict[int, PlayerProfile] = {}
        self.profiles_file = "player_profiles.json"
        self.load_profiles()
    
    def load_profiles(self):
        """Load profiles from file"""
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r') as f:
                    data = json.load(f)
                    for user_id_str, profile_dict in data.items():
                        user_id = int(user_id_str)
                        self.profiles[user_id] = PlayerProfile.from_dict(profile_dict)
                print(f"✅ Loaded {len(self.profiles)} player profiles")
            except Exception as e:
                print(f"Error loading profiles: {e}")
    
    def save_profiles(self):
        """Save profiles to file"""
        try:
            data = {str(uid): profile.to_dict() for uid, profile in self.profiles.items()}
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving profiles: {e}")
    
    def get_or_create_profile(self, user: discord.Member) -> PlayerProfile:
        """Get or create player profile"""
        if user.id not in self.profiles:
            self.profiles[user.id] = PlayerProfile(user.id, user.name)
        return self.profiles[user.id]
    
    def validate_banner_url(self, url: str) -> bool:
        """Validate if URL is a Discord CDN link"""
        valid_domains = ['cdn.discordapp.com', 'media.discordapp.net']
        return any(domain in url for domain in valid_domains)


def create_profile_embed(user: discord.Member, profile: PlayerProfile, 
                         multi_mode_stats) -> discord.Embed:
    """Create beautiful profile embed with all stats"""
    
    # Get stats from all modes
    all_stats = multi_mode_stats.get_all_modes_summary(user)
    
    # Create embed with banner if set
    embed = discord.Embed(
        title=f"🎮 {user.display_name}'s Profile",
        color=discord.Color.purple()
    )
    
    # Set banner image if available
    if profile.banner_url:
        embed.set_image(url=profile.banner_url)
    
    # Set user avatar as thumbnail
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    
    # Bio section
    if profile.bio:
        embed.add_field(
            name="📝 Bio",
            value=f"```\n{profile.bio}\n```",
            inline=False
        )
    
    # Mains section
    mains_text = ""
    if profile.main_killer:
        mains_text += f"⚔️ **Killer Main:** {profile.main_killer}\n"
    if profile.main_survivor:
        mains_text += f"🏃 **Survivor Main:** {profile.main_survivor}\n"
    
    if mains_text:
        embed.add_field(
            name="🎯 Mains",
            value=mains_text,
            inline=False
        )
    
    # Detailed stats section
    stats_text = f"⏱️ **Playtime:** {profile.playtime_hours} hours\n"
    stats_text += f"⚔️ **Killer Wins:** {profile.killer_wins}\n"
    stats_text += f"🏃 **Survivor Wins:** {profile.survivor_wins}\n"
    
    embed.add_field(
        name="📊 Detailed Stats",
        value=stats_text,
        inline=True
    )
    
    # Mode stats summary
    mode_summary = []
    for mode in ["1v1", "2v2", "3v3", "4v4", "5v5"]:
        if mode in all_stats:
            stats = all_stats[mode]
            total_games = stats.wins + stats.losses
            if total_games > 0:
                winrate = (stats.wins / total_games) * 100
                mode_summary.append(f"**{mode}:** {stats.points}pts ({winrate:.0f}% WR)")
    
    if mode_summary:
        embed.add_field(
            name="🏆 Mode Stats",
            value="\n".join(mode_summary),
            inline=True
        )
    
    # Footer with last update
    embed.set_footer(text=f"Profile last updated: {profile.last_updated.strftime('%Y-%m-%d')}")
    
    return embed


def create_simple_profile_card(user: discord.Member, profile: PlayerProfile) -> str:
    """Create ASCII art profile card for text display"""
    
    card = f"""
╔═══════════════════════════════════════════════════╗
║  🎮 {user.display_name.center(42)} ║
╠═══════════════════════════════════════════════════╣
║                                                   ║
"""
    
    if profile.bio:
        bio_lines = textwrap.wrap(profile.bio, width=45)
        for line in bio_lines[:3]:  # Max 3 lines
            card += f"║  {line.ljust(47)} ║\n"
        card += "║                                                   ║\n"
    
    card += "╠═══════════════════════════════════════════════════╣\n"
    
    if profile.main_killer:
        card += f"║  ⚔️  Killer Main: {profile.main_killer.ljust(31)} ║\n"
    if profile.main_survivor:
        card += f"║  🏃 Survivor Main: {profile.main_survivor.ljust(29)} ║\n"
    
    card += "╠═══════════════════════════════════════════════════╣\n"
    card += f"║  ⏱️  Playtime: {str(profile.playtime_hours).ljust(34)} hours ║\n"
    card += f"║  ⚔️  Killer Wins: {str(profile.killer_wins).ljust(32)} ║\n"
    card += f"║  🏃 Survivor Wins: {str(profile.survivor_wins).ljust(29)} ║\n"
    card += "╚═══════════════════════════════════════════════════╝"
    
    return card


async def handle_profile_banner_set(interaction: discord.Interaction, profile_system: ProfileSystem, 
                                    banner_url: str):
    """Set profile banner"""
    profile = profile_system.get_or_create_profile(interaction.user)
    
    # Validate URL
    if not profile_system.validate_banner_url(banner_url):
        await interaction.response.send_message(
            "❌ Please use a Discord CDN link (cdn.discordapp.com or media.discordapp.net)\n"
            "Upload an image in Discord, then right-click → Copy Link",
            ephemeral=True
        )
        return
    
    # Test if URL is accessible
    try:
        response = requests.head(banner_url, timeout=5)
        if response.status_code != 200:
            await interaction.response.send_message(
                "❌ Unable to access that image URL. Make sure it's a valid Discord CDN link.",
                ephemeral=True
            )
            return
    except:
        await interaction.response.send_message(
            "❌ Unable to access that image URL. Make sure it's a valid Discord CDN link.",
            ephemeral=True
        )
        return
    
    profile.banner_url = banner_url
    profile.last_updated = datetime.now()
    profile_system.save_profiles()
    
    await interaction.response.send_message(
        "✅ Profile banner updated! View it with `/stats`",
        ephemeral=False
    )


async def handle_profile_bio_set(interaction: discord.Interaction, profile_system: ProfileSystem, 
                                 bio: str):
    """Set profile bio"""
    profile = profile_system.get_or_create_profile(interaction.user)
    
    # Limit bio length
    if len(bio) > 200:
        await interaction.response.send_message(
            f"❌ Bio too long! Maximum 200 characters. (Current: {len(bio)})",
            ephemeral=True
        )
        return
    
    profile.bio = bio
    profile.last_updated = datetime.now()
    profile_system.save_profiles()
    
    await interaction.response.send_message(
        "✅ Profile bio updated! View it with `/stats`",
        ephemeral=False
    )


async def handle_profile_main_set(interaction: discord.Interaction, profile_system: ProfileSystem,
                                  character_type: str, character_name: str):
    """Set main killer or survivor"""
    from team_matchmaking_part10 import SURVIVORS, KILLERS
    
    profile = profile_system.get_or_create_profile(interaction.user)
    
    # Validate character
    if character_type == "killer":
        if character_name not in KILLERS:
            await interaction.response.send_message(
                f"❌ Invalid killer: {character_name}\nAvailable: {', '.join(KILLERS)}",
                ephemeral=True
            )
            return
        profile.main_killer = character_name
        message = f"✅ Killer main set to **{character_name}**!"
    else:  # survivor
        if character_name not in SURVIVORS:
            await interaction.response.send_message(
                f"❌ Invalid survivor: {character_name}\nAvailable: {', '.join(SURVIVORS)}",
                ephemeral=True
            )
            return
        profile.main_survivor = character_name
        message = f"✅ Survivor main set to **{character_name}**!"
    
    profile.last_updated = datetime.now()
    profile_system.save_profiles()
    
    await interaction.response.send_message(message, ephemeral=False)


async def handle_profile_stats_set(interaction: discord.Interaction, profile_system: ProfileSystem,
                                   stat_type: str, value: int):
    """Set playtime, killer wins, or survivor wins"""
    profile = profile_system.get_or_create_profile(interaction.user)
    
    if value < 0:
        await interaction.response.send_message("❌ Value cannot be negative!", ephemeral=True)
        return
    
    if stat_type == "playtime":
        profile.playtime_hours = value
        message = f"✅ Playtime set to **{value} hours**!"
    elif stat_type == "killerwin":
        profile.killer_wins = value
        message = f"✅ Killer wins set to **{value}**!"
    elif stat_type == "survivorwin":
        profile.survivor_wins = value
        message = f"✅ Survivor wins set to **{value}**!"
    else:
        await interaction.response.send_message("❌ Invalid stat type!", ephemeral=True)
        return
    
    profile.last_updated = datetime.now()
    profile_system.save_profiles()
    
    await interaction.response.send_message(message, ephemeral=False)
