"""
TEAM MATCHMAKING SYSTEM - PART 11 (FIXED V2)
5v5 Tournament Matchmaking & Game Flow
Handles /challenge system and phase progression with thread creation
Updated to work with score-based results system
"""

import discord
from discord import app_commands
from typing import Optional, Dict
from team_matchmaking_part10 import (
    Tournament5v5Match, 
    MAPS, 
    KILLERS, 
    SURVIVORS,
    MAP_KILLER_RECOMMENDATIONS,
    KILLER_BAN_RECOMMENDATIONS,
    TOURNAMENT_WIN_POINTS,
    TOURNAMENT_LOSS_POINTS
)


class Tournament5v5System:
    """Manages 5v5 tournament matches"""
    def __init__(self, party_system):
        self.party_system = party_system
        self.pending_challenges: Dict[int, int] = {}  # challenger_host_id -> challenged_host_id
        self.active_matches: Dict[int, Tournament5v5Match] = {}  # thread_id -> Match
        self.ALLOWED_CHANNEL_ID = 1465766701814517770
    
    async def send_challenge(self, interaction: discord.Interaction, opponent: discord.Member):
        """Host challenges another party host to 5v5"""
        # Check channel
        if interaction.channel_id != self.ALLOWED_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 5v5 can only be used in <#{self.ALLOWED_CHANNEL_ID}>!",
                ephemeral=True
            )
            return
        
        user = interaction.user
        
        # Check if user has a party
        party = self.party_system.get_user_party(user)
        if not party:
            await interaction.response.send_message("❌ You need a party first! Use `/party`", ephemeral=True)
            return
        
        # Must be host
        if not party.is_host(user):
            await interaction.response.send_message("❌ Only party host can challenge!", ephemeral=True)
            return
        
        # Party must have exactly 5 members
        if party.get_size() != 5:
            await interaction.response.send_message(
                f"❌ You need exactly 5 members for 5v5! (Current: {party.get_size()})",
                ephemeral=True
            )
            return
        
        # Check opponent has a party
        opponent_party = self.party_system.get_user_party(opponent)
        if not opponent_party:
            await interaction.response.send_message(f"❌ {opponent.mention} doesn't have a party!", ephemeral=True)
            return
        
        if not opponent_party.is_host(opponent):
            await interaction.response.send_message(f"❌ {opponent.mention} is not a party host!", ephemeral=True)
            return
        
        if opponent_party.get_size() != 5:
            await interaction.response.send_message(
                f"❌ {opponent.mention}'s party needs exactly 5 members! (Current: {opponent_party.get_size()})",
                ephemeral=True
            )
            return
        
        # Can't challenge yourself
        if user.id == opponent.id:
            await interaction.response.send_message("❌ You can't challenge yourself!", ephemeral=True)
            return
        
        # Check if already in a match
        for match in self.active_matches.values():
            if user.id in [m.id for m in match.team_a + match.team_b]:
                await interaction.response.send_message("❌ You're already in a 5v5 match!", ephemeral=True)
                return
        
        # Send challenge
        self.pending_challenges[user.id] = opponent.id
        
        embed = discord.Embed(
            title="⚔️ 5v5 TOURNAMENT CHALLENGE!",
            description=f"**{user.mention}** challenges **{opponent.mention}** to a 5v5 tournament!",
            color=discord.Color.orange()
        )
        
        # Show both teams with party names
        team_a_text = f"**Party: {party.party_name}**\n"
        team_a_text += "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" for i, m in enumerate(party.members)])
        
        team_b_text = f"**Party: {opponent_party.party_name}**\n"
        team_b_text += "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" for i, m in enumerate(opponent_party.members)])
        
        embed.add_field(name="🔵 Team A (Challenger)", value=team_a_text, inline=True)
        embed.add_field(name="🔴 Team B (Challenged)", value=team_b_text, inline=True)
        embed.add_field(
            name="Format",
            value="**10 rounds** | Best of 10 wins\nHosts select maps, bans, and killer players\nPlayers pick their survivors\n**Score each round: 0-7 points**",
            inline=False
        )
        embed.set_footer(text=f"{opponent.name}, use /acceptchallenge @{user.name} to accept!")
        
        await interaction.response.send_message(embed=embed)
    
    async def accept_challenge(self, interaction: discord.Interaction, challenger: discord.Member):
        """Accept a 5v5 challenge"""
        user = interaction.user
        
        # Check if there's a pending challenge
        if challenger.id not in self.pending_challenges:
            await interaction.response.send_message(
                f"❌ No pending challenge from {challenger.mention}!",
                ephemeral=True
            )
            return
        
        if self.pending_challenges[challenger.id] != user.id:
            await interaction.response.send_message(
                f"❌ {challenger.mention} didn't challenge you!",
                ephemeral=True
            )
            return
        
        # Get parties
        challenger_party = self.party_system.get_user_party(challenger)
        accepter_party = self.party_system.get_user_party(user)
        
        if not challenger_party or not accepter_party:
            await interaction.response.send_message("❌ One of the parties no longer exists!", ephemeral=True)
            del self.pending_challenges[challenger.id]
            return
        
        # Verify sizes
        if challenger_party.get_size() != 5 or accepter_party.get_size() != 5:
            await interaction.response.send_message("❌ Both parties must have exactly 5 members!", ephemeral=True)
            del self.pending_challenges[challenger.id]
            return
        
        # Create match
        await self.create_tournament_match(
            interaction,
            list(challenger_party.members),
            list(accepter_party.members),
            challenger_party.party_name,
            accepter_party.party_name
        )
        
        # Remove challenge
        del self.pending_challenges[challenger.id]
    
    async def create_tournament_match(self, interaction: discord.Interaction, 
                                     team_a: list, team_b: list,
                                     team_a_name: str, team_b_name: str):
        """Create a 5v5 tournament match with proper thread"""
        match = Tournament5v5Match(team_a, team_b, team_a_name, team_b_name, interaction.channel)
        
        # Create starting embed
        embed = discord.Embed(
            title="⚔️ 5v5 TOURNAMENT STARTING!",
            description=f"**{team_a_name}** vs **{team_b_name}**\n\n10 rounds of intense 1v5 combat!\n**Each round scored 0-7 points**",
            color=discord.Color.gold()
        )
        
        team_a_text = "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" for i, m in enumerate(team_a)])
        team_b_text = "\n".join([f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}" for i, m in enumerate(team_b)])
        
        embed.add_field(name=f"🔵 {team_a_name}", value=team_a_text, inline=True)
        embed.add_field(name=f"🔴 {team_b_name}", value=team_b_text, inline=True)
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Create thread with party names
        thread = await message.create_thread(
            name=f"⚔️ {team_a_name} vs {team_b_name}",
            auto_archive_duration=1440
        )
        
        match.thread = thread
        self.active_matches[thread.id] = match
        
        # Mention all players in thread
        all_players = " ".join([m.mention for m in team_a + team_b])
        await thread.send(f"📢 {all_players}\n\nWelcome to the tournament! Let's begin!")
        
        # Start first round
        await self.start_round(match)
    
    async def start_round(self, match: Tournament5v5Match):
        """Start a new round"""
        thread = match.thread
        
        attacking_team = match.get_attacking_team()
        defending_team = match.get_defending_team()
        attacking_host = match.get_attacking_host()
        defending_host = match.get_defending_host()
        
        # Announce round
        embed = discord.Embed(
            title=f"🎮 ROUND {match.current_round}/10",
            description=f"**Score:** {match.team_a_name} {match.team_a_score} - {match.team_b_score} {match.team_b_name}",
            color=discord.Color.blue()
        )
        
        attacking_team_name = match.get_team_name(attacking_team)
        defending_team_name = match.get_team_name(defending_team)
        
        embed.add_field(
            name="⚔️ Attacking (Killer)",
            value=f"**{attacking_team_name}**\nHost: {attacking_host.mention}",
            inline=True
        )
        embed.add_field(
            name="🛡️ Defending (Survivors)",
            value=f"**{defending_team_name}**\nHost: {defending_host.mention}",
            inline=True
        )
        embed.add_field(
            name="📋 Phase 1: Map Selection",
            value=f"{attacking_host.mention} use `/selectmap <map>` to choose the map!",
            inline=False
        )
        
        await thread.send(embed=embed)
        
        match.current_phase = "map_select"
        await self.update_status_message(match)
    
    async def update_status_message(self, match: Tournament5v5Match):
        """Update or create status message"""
        embed = self.create_status_embed(match)
        
        if match.status_message:
            try:
                await match.status_message.edit(embed=embed)
            except:
                match.status_message = await match.thread.send(embed=embed)
        else:
            match.status_message = await match.thread.send(embed=embed)
    
    def create_status_embed(self, match: Tournament5v5Match) -> discord.Embed:
        """Create status embed for current round"""
        embed = discord.Embed(
            title=f"📊 Round {match.current_round} Status",
            color=discord.Color.gold()
        )
        
        # Phase indicator
        phase_text = {
            "map_select": "🗺️ MAP SELECTION",
            "killer_select": "⚔️ KILLER SELECTION",
            "ban": "🚫 BAN PHASE",
            "pick": "✅ PICK PHASE",
            "results": "📊 AWAITING RESULTS"
        }.get(match.current_phase, "Unknown")
        
        embed.description = f"**Phase:** {phase_text}\n**Score:** {match.team_a_name} {match.team_a_score} - {match.team_b_score} {match.team_b_name}"
        
        # Show round info
        if match.selected_map:
            embed.add_field(name="🗺️ Map", value=match.selected_map, inline=True)
        
        if match.selected_killer_character:
            attacking_members = match.get_team_members(match.get_attacking_team())
            killer_player = attacking_members[match.selected_killer_player_index]
            embed.add_field(
                name="⚔️ Killer",
                value=f"Player {match.selected_killer_player_index + 1}: {killer_player.mention}\n**{match.selected_killer_character}**",
                inline=True
            )
        
        if match.banned_survivors:
            embed.add_field(
                name="🚫 Banned Survivors",
                value=", ".join(match.banned_survivors) + f" ({len(match.banned_survivors)}/{2})",
                inline=False
            )
        
        if match.round_survivor_picks:
            defending_members = match.get_team_members(match.get_defending_team())
            picks_text = []
            for i in range(5):
                player = defending_members[i]
                pick = match.round_survivor_picks.get(i, "❌")
                picks_text.append(f"Player {i+1} ({player.display_name}): {pick}")
            
            embed.add_field(
                name=f"🛡️ Survivor Picks ({len(match.round_survivor_picks)}/5)",
                value="\n".join(picks_text),
                inline=False
            )
        
        return embed
