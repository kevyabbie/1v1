"""
TEAM MATCHMAKING SYSTEM - PART 3
Queue System
Manages matchmaking queues for 2v2, 3v3, 4v4
"""

import discord
from typing import Dict, Optional, List, Tuple
from team_matchmaking_part2 import TeamMatch
import random


class TeamQueue:
    """Queue for team matchmaking"""
    def __init__(self, mode: str):
        self.mode = mode
        self.waiting_teams: Dict[int, List[discord.Member]] = {}  # host_id -> team
        self.team_sizes = {"2v2": 2, "3v3": 3, "4v4": 4}
        self.required_size = self.team_sizes[mode]
    
    def add_team(self, host: discord.Member, team: List[discord.Member]) -> bool:
        """Add team to queue"""
        if host.id in self.waiting_teams:
            return False
        self.waiting_teams[host.id] = team
        return True
    
    def remove_team(self, host_id: int) -> bool:
        """Remove team from queue"""
        if host_id in self.waiting_teams:
            del self.waiting_teams[host_id]
            return True
        return False
    
    def find_match(self, host_id: int) -> Optional[Tuple]:
        """Find a match for the team"""
        if host_id not in self.waiting_teams:
            return None
        
        team_a = self.waiting_teams[host_id]
        
        # Find another team
        for other_host_id, team_b in self.waiting_teams.items():
            if other_host_id != host_id:
                # Match found!
                del self.waiting_teams[host_id]
                del self.waiting_teams[other_host_id]
                return (team_a, team_b)
        
        return None


class TeamMatchmakingSystem:
    """Manages team matchmaking for all modes"""
    def __init__(self, party_system):
        self.party_system = party_system
        self.queues = {
            "2v2": TeamQueue("2v2"),
            "3v3": TeamQueue("3v3"),
            "4v4": TeamQueue("4v4")
        }
        self.active_matches: Dict[int, TeamMatch] = {}  # thread_id -> TeamMatch
        self.ALLOWED_CHANNELS = {
            "2v2": 1465766622038986784,
            "3v3": 1465766649956143205,
            "4v4": 1465766666326638839
        }
        self.multi_mode_stats = None  # Will be linked later
    
    async def queue_for_match(self, interaction: discord.Interaction, mode: str):
        """Queue a party for team matchmaking"""
        # Check channel - each mode has its own channel
        allowed_channel = self.ALLOWED_CHANNELS.get(mode)
        if interaction.channel_id != allowed_channel:
            await interaction.response.send_message(
                f"❌ {mode.upper()} matchmaking can only be used in <#{allowed_channel}>!",
                ephemeral=True
            )
            return
        
        user = interaction.user
        
        # Get user's party
        party = self.party_system.get_user_party(user)
        if not party:
            await interaction.response.send_message(
                "❌ You need a party first! Use `/party` to create one.",
                ephemeral=True
            )
            return
        
        # Must be host
        if not party.is_host(user):
            await interaction.response.send_message(
                "❌ Only the party host can queue for matches!",
                ephemeral=True
            )
            return
        
        # Check party size
        required_size = {"2v2": 2, "3v3": 3, "4v4": 4}[mode]
        party_size = party.get_size()
        
        if party_size > required_size:
            await interaction.response.send_message(
                f"❌ Party too large for {mode}! Need exactly {required_size}, have {party_size}.\n"
                f"Kick extra members with `/partykick`.",
                ephemeral=True
            )
            return
        
        # Auto-fill with random players if needed
        team = list(party.members)
        if party_size < required_size:
            # For now, just require exact size
            await interaction.response.send_message(
                f"❌ Party too small for {mode}! Need {required_size}, have {party_size}.\n"
                f"Invite more members with `/partyinvite`.",
                ephemeral=True
            )
            return
        
        # Add to queue
        queue = self.queues[mode]
        if not queue.add_team(user, team):
            await interaction.response.send_message(
                f"❌ You're already in the {mode} queue!",
                ephemeral=True
            )
            return
        
        # Try to find match
        match_result = queue.find_match(user.id)
        
        if match_result:
            # Match found!
            team_a, team_b = match_result
            await self.create_team_match(interaction, team_a, team_b, mode)
        else:
            # Waiting for opponent
            embed = discord.Embed(
                title=f"🔍 {mode.upper()} Matchmaking",
                description=f"**{user.display_name}'s team** is searching for opponents!",
                color=discord.Color.blue()
            )
            
            team_text = "\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(team)])
            embed.add_field(name="Your Team", value=team_text, inline=False)
            embed.add_field(name="Status", value="⏳ Waiting for another team...", inline=False)
            
            await interaction.response.send_message(embed=embed)
    
    async def cancel_queue(self, interaction: discord.Interaction):
        """Cancel queue"""
        user = interaction.user
        
        # Check all queues
        for mode, queue in self.queues.items():
            if queue.remove_team(user.id):
                await interaction.response.send_message(
                    f"✅ Removed from {mode} queue.",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            "❌ You're not in any queue!",
            ephemeral=True
        )
    
    async def create_team_match(self, interaction: discord.Interaction,
                                team_a: List[discord.Member], team_b: List[discord.Member],
                                mode: str):
        """Create a team match"""
        match = TeamMatch(team_a, team_b, mode, interaction.channel)
        
        # Create embed
        embed = discord.Embed(
            title=f"⚔️ {mode.upper()} Match Starting!",
            color=discord.Color.green()
        )
        
        team_a_text = "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" 
                                 for i, m in enumerate(team_a)])
        team_b_text = "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" 
                                 for i, m in enumerate(team_b)])
        
        embed.add_field(name="🔵 Team A", value=team_a_text, inline=True)
        embed.add_field(name="🔴 Team B", value=team_b_text, inline=True)
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Create thread
        thread = await message.create_thread(
            name=f"⚔️ {mode.upper()}: {team_a[0].display_name} vs {team_b[0].display_name}",
            auto_archive_duration=60
        )
        
        match.thread = thread
        self.active_matches[thread.id] = match
        
        # Start match
        await self.start_match_phases(match)
    
    async def start_match_phases(self, match: TeamMatch):
        """Start ban/pick phases"""
        thread = match.thread
        
        if match.current_phase == "ban":
            await thread.send(
                f"🚫 **BAN PHASE**\n"
                f"Hosts use `/teamban <character>` to ban!\n"
                f"Each team can ban {match.get_ban_limit()} character(s)."
            )
        else:
            await thread.send(
                f"🎯 **PICK PHASE - Round 1**\n"
                f"Use `/teampick <character>` to pick your character!\n"
                f"Check your role assignment below."
            )
        
        await self.update_match_status(match)
    
    async def update_match_status(self, match: TeamMatch):
        """Update match status message"""
        # Implementation in Part 4
        pass
