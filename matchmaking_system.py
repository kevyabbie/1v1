"""
1v1 Matchmaking System for Discord Bot
Handles matchmaking, ban/pick phases, and point tracking
WITH AUTOCOMPLETE OPTIONS FOR BAN/PICK
FIXED: Round-by-round scoring and correct pick order
"""

import discord
from discord import app_commands
from typing import Optional, Dict, List
import json
import os
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

# Game Constants
MAX_PICKS = 3
MAX_BANS = 2
WIN_POINTS = 15
LOSS_POINTS = -15
CANCEL_PENALTY = -8


class PlayerStats:
    """Track player statistics"""
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.points = 0
        self.wins = 0
        self.losses = 0
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'points': self.points,
            'wins': self.wins,
            'losses': self.losses
        }
    
    @classmethod
    def from_dict(cls, data):
        stats = cls(data['user_id'], data['username'])
        stats.points = data['points']
        stats.wins = data['wins']
        stats.losses = data['losses']
        return stats


class Match:
    """Represents a 1v1 match"""
    def __init__(self, player1: discord.Member, channel: discord.TextChannel):
        self.player1 = player1
        self.player2: Optional[discord.Member] = None
        self.channel = channel
        self.thread: Optional[discord.Thread] = None
        self.waiting_message: Optional[discord.Message] = None
        
        # Ban/Pick tracking
        self.current_round = 1
        self.current_phase = "ban"  # "ban", "pick", or "results"
        self.current_turn: Optional[discord.Member] = None
        
        # Bans and Picks (player_id -> list)
        self.player1_bans: List[str] = []
        self.player2_bans: List[str] = []
        self.player1_picks: List[str] = []
        self.player2_picks: List[str] = []
        
        # Match results - UPDATED TO TRACK ROUND WINS
        self.player1_score = 0  # Track actual round wins
        self.player2_score = 0
        self.rounds_completed = 0  # How many rounds have been fully reported
        self.player1_claimed: Optional[str] = None  # "win" or "loss" for current round
        self.player2_claimed: Optional[str] = None
        self.match_complete = False
        
        self.status_message: Optional[discord.Message] = None
    
    def get_available_items(self, item_type: str) -> List[str]:
        """Get available items for picking (excluding banned)"""
        all_items = SURVIVORS if item_type == "survivor" else KILLERS
        banned = self.player1_bans + self.player2_bans
        return [item for item in all_items if item not in banned]
    
    def get_current_player_role(self) -> str:
        """
        Get what the current player should pick (killer/survivor)
        FIXED PATTERN:
        Round 1: P1 picks Killer, P2 picks Survivor
        Round 2: P2 picks Killer, P1 picks Survivor
        Round 3: P1 picks Killer, P2 picks Survivor
        """
        if self.current_round == 1:
            # Round 1: P1 = Killer, P2 = Survivor
            return "killer" if self.current_turn == self.player1 else "survivor"
        elif self.current_round == 2:
            # Round 2: P2 = Killer, P1 = Survivor
            return "survivor" if self.current_turn == self.player1 else "killer"
        else:  # Round 3
            # Round 3: P1 = Killer, P2 = Survivor
            return "killer" if self.current_turn == self.player1 else "survivor"


class MatchmakingSystem:
    """Main matchmaking system"""
    def __init__(self, bot_client):
        self.client = bot_client
        self.active_matches: Dict[int, Match] = {}  # channel_id -> Match
        self.waiting_players: Dict[int, Match] = {}  # channel_id -> Match
        self.player_stats: Dict[int, PlayerStats] = {}  # user_id -> PlayerStats
        self.stats_file = "player_stats.json"
        self.load_stats()
    
    def load_stats(self):
        """Load player statistics from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    for user_id_str, stats_dict in data.items():
                        user_id = int(user_id_str)
                        self.player_stats[user_id] = PlayerStats.from_dict(stats_dict)
            except Exception as e:
                print(f"Error loading stats: {e}")
    
    def save_stats(self):
        """Save player statistics to file"""
        try:
            data = {str(uid): stats.to_dict() for uid, stats in self.player_stats.items()}
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving stats: {e}")
    
    def get_or_create_stats(self, user: discord.Member) -> PlayerStats:
        """Get or create player stats"""
        if user.id not in self.player_stats:
            self.player_stats[user.id] = PlayerStats(user.id, user.name)
        return self.player_stats[user.id]
    
    async def start_matchmaking(self, interaction: discord.Interaction):
        """Start looking for a match"""
        # RESTRICTION: Only allow matchmaking in specific channel
        ALLOWED_CHANNEL_ID = 1465526001110093834
        
        if interaction.channel_id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Matchmaking can only be used in <#{ALLOWED_CHANNEL_ID}>!",
                ephemeral=True
            )
            return
        
        channel_id = interaction.channel_id
        user = interaction.user
        
        # Check if player already in a match
        for match in self.active_matches.values():
            if match.player1.id == user.id or (match.player2 and match.player2.id == user.id):
                await interaction.response.send_message(
                    "❌ You're already in an active match!", 
                    ephemeral=True
                )
                return
        
        # Check if someone is waiting
        if channel_id in self.waiting_players:
            existing_match = self.waiting_players[channel_id]
            
            # Can't match with yourself
            if existing_match.player1.id == user.id:
                await interaction.response.send_message(
                    "❌ You're already waiting for an opponent!", 
                    ephemeral=True
                )
                return
            
            # Match found!
            existing_match.player2 = user
            del self.waiting_players[channel_id]
            
            # Update the waiting message
            await existing_match.waiting_message.edit(
                embed=self.create_match_found_embed(existing_match)
            )
            
            # Create thread for the match
            thread = await existing_match.waiting_message.create_thread(
                name=f"⚔ {existing_match.player1.display_name} vs {existing_match.player2.display_name}",
                auto_archive_duration=60
            )
            existing_match.thread = thread
            
            # Move to active matches
            self.active_matches[thread.id] = existing_match
            
            # Start ban phase
            await self.start_ban_pick_phase(existing_match)
            
            await interaction.response.send_message(
                f"✅ Match found! Check the thread: {thread.mention}",
                ephemeral=True
            )
        
        else:
            # Create new waiting match
            match = Match(user, interaction.channel)
            
            embed = self.create_waiting_embed(match)
            await interaction.response.send_message(embed=embed)
            
            message = await interaction.original_response()
            match.waiting_message = message
            
            self.waiting_players[channel_id] = match
    
    def create_waiting_embed(self, match: Match) -> discord.Embed:
        """Create embed for waiting player"""
        embed = discord.Embed(
            title="🔍 1v1 Matchmaking",
            description=f"**{match.player1.display_name}** is looking for an opponent!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Current Match",
            value=f"```\n{match.player1.display_name} vs FINDING OPPONENT\n```",
            inline=False
        )
        embed.add_field(
            name="How to Join",
            value="Type `/1v1` to accept the challenge!",
            inline=False
        )
        return embed
    
    def create_match_found_embed(self, match: Match) -> discord.Embed:
        """Create embed when match is found"""
        embed = discord.Embed(
            title="⚔ Match Found!",
            description="Both players ready!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Match",
            value=f"```\n{match.player1.display_name} vs {match.player2.display_name}\n```",
            inline=False
        )
        embed.add_field(
            name="Players",
            value=f"**Player 1:** {match.player1.mention}\n**Player 2:** {match.player2.mention}",
            inline=False
        )
        return embed
    
    async def start_ban_pick_phase(self, match: Match):
        """Start the ban/pick phase in thread"""
        thread = match.thread
        
        # Welcome message
        await thread.send(
            f"Welcome {match.player1.mention} and {match.player2.mention}!\n"
            f"**Player 1:** {match.player1.display_name}\n"
            f"**Player 2:** {match.player2.display_name}\n\n"
            f"Starting **BAN PHASE**..."
        )
        
        # Start with Player 1 banning
        match.current_turn = match.player1
        match.current_phase = "ban"
        
        await self.update_status_message(match)
    
    async def update_status_message(self, match: Match):
        """Update or create the status message in thread"""
        embed = self.create_status_embed(match)
        
        if match.status_message:
            await match.status_message.edit(embed=embed)
        else:
            match.status_message = await match.thread.send(embed=embed)
    
    def create_status_embed(self, match: Match) -> discord.Embed:
        """Create status embed showing bans/picks"""
        embed = discord.Embed(
            title="🎮 BAN & PICK PHASE",
            color=discord.Color.gold()
        )
        
        # Show current phase
        if match.current_phase == "ban":
            phase_text = "BAN PHASE"
        elif match.current_phase == "pick":
            phase_text = f"PICK PHASE - Round {match.current_round}"
        else:  # results
            phase_text = f"RESULTS - Round {match.rounds_completed + 1}"
        
        embed.description = f"**Current Phase:** {phase_text}\n"
        
        # Show current score
        if match.rounds_completed > 0 or match.current_phase == "results":
            embed.description += f"**Score:** {match.player1_score}-{match.player2_score}\n"
        
        if match.current_turn and match.current_phase != "results":
            role = match.get_current_player_role() if match.current_phase == "pick" else None
            turn_text = f"**Turn:** {match.current_turn.mention}"
            if role:
                turn_text += f" (Picking {role.upper()})"
            embed.description += turn_text
        
        # Bans
        p1_bans_text = ", ".join(match.player1_bans) if match.player1_bans else "None"
        p2_bans_text = ", ".join(match.player2_bans) if match.player2_bans else "None"
        
        embed.add_field(
            name="🚫 Bans",
            value=f"**Player 1:** {p1_bans_text} ({len(match.player1_bans)}/{MAX_BANS})\n"
                  f"**Player 2:** {p2_bans_text} ({len(match.player2_bans)}/{MAX_BANS})",
            inline=False
        )
        
        # Picks
        p1_picks_text = ", ".join(match.player1_picks) if match.player1_picks else "None"
        p2_picks_text = ", ".join(match.player2_picks) if match.player2_picks else "None"
        
        embed.add_field(
            name="✅ Picks",
            value=f"**Player 1:** {p1_picks_text} ({len(match.player1_picks)}/{MAX_PICKS})\n"
                  f"**Player 2:** {p2_picks_text} ({len(match.player2_picks)}/{MAX_PICKS})",
            inline=False
        )
        
        # Available items
        if match.current_phase == "pick" and match.current_turn:
            role = match.get_current_player_role()
            available = match.get_available_items(role)
            if available:
                items_list = "\n".join([f"• {item}" for item in available[:10]])
                if len(available) > 10:
                    items_list += f"\n... and {len(available) - 10} more"
                embed.add_field(
                    name=f"📋 Available {role.capitalize()}s",
                    value=f"```\n{items_list}\n```",
                    inline=False
                )
        
        return embed
    
    async def handle_ban(self, interaction: discord.Interaction, item: str):
        """Handle ban command"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        # Check if it's ban phase
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        # Check if it's player's turn
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        # Determine which player
        is_player1 = user.id == match.player1.id
        player_bans = match.player1_bans if is_player1 else match.player2_bans
        
        # Check ban limit
        if len(player_bans) >= MAX_BANS:
            await interaction.response.send_message(f"❌ You've already banned {MAX_BANS} items!", ephemeral=True)
            return
        
        # Normalize input (case-insensitive, space-insensitive)
        normalized_input = item.lower().replace(" ", "")
        
        # Find matching item from the list
        all_items = SURVIVORS + KILLERS
        matched_item = None
        for valid_item in all_items:
            if valid_item.lower().replace(" ", "") == normalized_input:
                matched_item = valid_item
                break
        
        # Validate item
        if not matched_item:
            await interaction.response.send_message(f"❌ Invalid item: {item}", ephemeral=True)
            return
        
        # Check if already banned
        if matched_item in match.player1_bans or matched_item in match.player2_bans:
            await interaction.response.send_message(f"❌ {matched_item} is already banned!", ephemeral=True)
            return
        
        # Add ban (using the properly formatted name)
        player_bans.append(matched_item)
        
        # Announce the ban publicly in the thread
        player_label = "Player 1" if is_player1 else "Player 2"
        await interaction.response.send_message(
            f"🚫 **{player_label}** ({user.mention}) banned **{matched_item}**!",
            ephemeral=False
        )
        
        # Check if both players finished banning
        if len(match.player1_bans) == MAX_BANS and len(match.player2_bans) == MAX_BANS:
            # Move to pick phase
            match.current_phase = "pick"
            match.current_round = 1
            match.current_turn = match.player1
            await match.thread.send("🎯 **BAN PHASE COMPLETE!** Starting **PICK PHASE - Round 1**...")
        else:
            # Switch turn
            match.current_turn = match.player2 if is_player1 else match.player1
        
        await self.update_status_message(match)
    
    async def handle_pick(self, interaction: discord.Interaction, item: str):
        """Handle pick command"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        # Check if it's pick phase
        if match.current_phase != "pick":
            await interaction.response.send_message("❌ Not in pick phase!", ephemeral=True)
            return
        
        # Check if it's player's turn
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        # Determine which player
        is_player1 = user.id == match.player1.id
        player_picks = match.player1_picks if is_player1 else match.player2_picks
        
        # Get required role for current player
        required_role = match.get_current_player_role()
        item_pool = KILLERS if required_role == "killer" else SURVIVORS
        
        # Normalize input (case-insensitive, space-insensitive)
        normalized_input = item.lower().replace(" ", "")
        
        # Find matching item from the pool
        matched_item = None
        for valid_item in item_pool:
            if valid_item.lower().replace(" ", "") == normalized_input:
                matched_item = valid_item
                break
        
        # Validate item
        if not matched_item:
            await interaction.response.send_message(
                f"❌ You must pick a **{required_role}**! {item} is not valid.",
                ephemeral=True
            )
            return
        
        # Check if banned
        if matched_item in match.player1_bans or matched_item in match.player2_bans:
            await interaction.response.send_message(f"❌ {matched_item} is banned!", ephemeral=True)
            return
        
        # Check if already picked
        if matched_item in match.player1_picks or matched_item in match.player2_picks:
            await interaction.response.send_message(f"❌ {matched_item} is already picked!", ephemeral=True)
            return
        
        # Add pick (using the properly formatted name)
        player_picks.append(matched_item)
        
        # Announce the pick publicly in the thread
        player_label = "Player 1" if is_player1 else "Player 2"
        await interaction.response.send_message(
            f"✅ **{player_label}** ({user.mention}) picked **{matched_item}** ({required_role.capitalize()})!",
            ephemeral=False
        )
        
        # Check round progression
        total_picks = len(match.player1_picks) + len(match.player2_picks)
        
        if total_picks == 6:  # All picks done (3 rounds x 2 players)
            match.current_phase = "results"
            await match.thread.send(
                "🎉 **PICK PHASE COMPLETE!**\n"
                f"**Current Score:** {match.player1_score}-{match.player2_score}\n"
                f"Play **Round {match.rounds_completed + 1}** and use `/iwon` or `/ilose` to report the result!"
            )
            await self.update_status_message(match)
        elif total_picks % 2 == 0:  # Round complete
            match.current_round += 1
            match.current_turn = match.player2 if match.current_round == 2 else match.player1  # FIXED: Round 2 starts with P2
            await match.thread.send(f"🔄 **Round {match.current_round} starting...**")
            await self.update_status_message(match)
        else:
            # Switch turn
            match.current_turn = match.player2 if is_player1 else match.player1
            await self.update_status_message(match)
    
    async def handle_result(self, interaction: discord.Interaction, result: str):
        """Handle win/loss claims - UPDATED FOR ROUND-BY-ROUND SCORING"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        # Check if pick phase is complete
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Complete the pick phase first!", ephemeral=True)
            return
        
        # Determine which player
        is_player1 = user.id == match.player1.id
        is_player2 = user.id == match.player2.id
        
        if not (is_player1 or is_player2):
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        # Record claim
        if is_player1:
            if match.player1_claimed:
                await interaction.response.send_message("❌ You already submitted your result for this round!", ephemeral=True)
                return
            match.player1_claimed = result
        else:
            if match.player2_claimed:
                await interaction.response.send_message("❌ You already submitted your result for this round!", ephemeral=True)
                return
            match.player2_claimed = result
        
        # Check if both submitted
        if match.player1_claimed and match.player2_claimed:
            # Validate results match
            valid = (
                (match.player1_claimed == "win" and match.player2_claimed == "loss") or
                (match.player1_claimed == "loss" and match.player2_claimed == "win")
            )
            
            if not valid:
                await interaction.response.send_message(
                    "⚠ **Results don't match!** Please verify who won this round.",
                    ephemeral=False
                )
                match.player1_claimed = None
                match.player2_claimed = None
                return
            
            # Determine round winner
            round_winner = match.player1 if match.player1_claimed == "win" else match.player2
            is_p1_winner = round_winner == match.player1
            
            # Update round score
            if is_p1_winner:
                match.player1_score += 1
            else:
                match.player2_score += 1
            
            match.rounds_completed += 1
            
            # Check if match is complete (best of 3)
            match_over = (match.player1_score == 2 or match.player2_score == 2 or match.rounds_completed == 3)
            
            if match_over:
                # Determine overall match winner
                if match.player1_score > match.player2_score:
                    winner = match.player1
                    loser = match.player2
                else:
                    winner = match.player2
                    loser = match.player1
                
                # Update stats
                winner_stats = self.get_or_create_stats(winner)
                loser_stats = self.get_or_create_stats(loser)
                
                winner_stats.points += WIN_POINTS
                winner_stats.wins += 1
                
                # Apply loss points but prevent going below 0
                loser_stats.points = max(0, loser_stats.points + LOSS_POINTS)
                loser_stats.losses += 1
                
                self.save_stats()
                
                # Create result embed
                embed = discord.Embed(
                    title="🏆 Match Complete!",
                    description=f"**{winner.display_name}** wins against **{loser.display_name}**!",
                    color=discord.Color.gold()
                )
                embed.add_field(
                    name="Final Score",
                    value=f"```\n{match.player1_score}-{match.player2_score}\n```",
                    inline=False
                )
                
                # Calculate actual points change for display
                loser_points_change = loser_stats.points - (loser_stats.points - LOSS_POINTS if loser_stats.points >= abs(LOSS_POINTS) else loser_stats.points)
                
                embed.add_field(
                    name="Points",
                    value=f"**{winner.display_name}:** +{WIN_POINTS} points (Total: {winner_stats.points})\n"
                          f"**{loser.display_name}:** {LOSS_POINTS} points (Total: {loser_stats.points})",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Clean up
                match.match_complete = True
                del self.active_matches[thread_id]
                
                # Archive thread after 5 minutes
                await match.thread.edit(auto_archive_duration=5)
            else:
                # More rounds to play
                round_loser = match.player2 if is_p1_winner else match.player1
                
                embed = discord.Embed(
                    title=f"✅ Round {match.rounds_completed} Complete!",
                    description=f"**{round_winner.display_name}** won this round!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Current Score",
                    value=f"```\n{match.player1_score}-{match.player2_score}\n```",
                    inline=False
                )
                embed.add_field(
                    name="Next Round",
                    value=f"Play **Round {match.rounds_completed + 1}** now!\nUse `/iwon` or `/ilose` to report the result.",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Reset claims for next round
                match.player1_claimed = None
                match.player2_claimed = None
                
                await self.update_status_message(match)
        
        else:
            # Waiting for other player
            waiting_for = match.player2 if is_player1 else match.player1
            current_score = f"{match.player1_score}-{match.player2_score}"
            await interaction.response.send_message(
                f"✅ You claimed a **{result}** for Round {match.rounds_completed + 1}.\n"
                f"**Current Score:** {current_score}\n"
                f"Waiting for {waiting_for.mention} to submit their result.",
                ephemeral=False
            )
    
    async def handle_cancel(self, interaction: discord.Interaction):
        """Handle match cancellation - UPDATED WITH PENALTY"""
        thread_id = interaction.channel_id
        user = interaction.user
        
        # Check if in an active match
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        
        # Check if user is in this match
        if user.id != match.player1.id and user.id != match.player2.id:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        # Get player info
        canceller = match.player1 if user.id == match.player1.id else match.player2
        other_player = match.player2 if user.id == match.player1.id else match.player1
        
        # Apply penalty to canceller but prevent going below 0
        canceller_stats = self.get_or_create_stats(canceller)
        canceller_stats.points = max(0, canceller_stats.points + CANCEL_PENALTY)
        self.save_stats()
        
        # Cancel the match
        embed = discord.Embed(
            title="❌ Match Cancelled",
            description=f"Match cancelled by **{canceller.display_name}**.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Penalty",
            value=f"**{canceller.display_name}:** {CANCEL_PENALTY} points (Total: {canceller_stats.points})\n"
                  f"**{other_player.display_name}:** No penalty",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Clean up
        del self.active_matches[thread_id]
        
        # Archive thread
        await match.thread.edit(archived=True)
    
    async def cleanup_waiting_match(self, channel_id: int):
        """Clean up a waiting match (when thread is closed before match starts)"""
        if channel_id in self.waiting_players:
            del self.waiting_players[channel_id]


# Setup function to add commands to bot
def setup_matchmaking(bot_client, tree: app_commands.CommandTree):
    """Setup matchmaking commands"""
    matchmaking = MatchmakingSystem(bot_client)
    
    @tree.command(name="1v1", description="Start or join a 1v1 match")
    async def start_1v1(interaction: discord.Interaction):
        await matchmaking.start_matchmaking(interaction)
    
    @tree.command(name="ban", description="Ban an item during ban phase")
    @app_commands.describe(item="Item to ban")
    async def ban_item(interaction: discord.Interaction, item: str):
        await matchmaking.handle_ban(interaction, item)
    
    @ban_item.autocomplete('item')
    async def ban_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for ban command showing all available items"""
        thread_id = interaction.channel_id
        
        # Get all items
        all_items = SURVIVORS + KILLERS
        
        # If in an active match, exclude already banned items
        if thread_id in matchmaking.active_matches:
            match = matchmaking.active_matches[thread_id]
            banned_items = match.player1_bans + match.player2_bans
            all_items = [item for item in all_items if item not in banned_items]
        
        # Filter by current input
        if current:
            filtered = [item for item in all_items if current.lower() in item.lower()]
        else:
            filtered = all_items
        
        # Return top 25 matches (Discord limit)
        return [
            app_commands.Choice(name=item, value=item)
            for item in filtered[:25]
        ]
    
    @tree.command(name="pick", description="Pick an item during pick phase")
    @app_commands.describe(item="Item to pick")
    async def pick_item(interaction: discord.Interaction, item: str):
        await matchmaking.handle_pick(interaction, item)
    
    @pick_item.autocomplete('item')
    async def pick_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for pick command showing only available items for current role"""
        thread_id = interaction.channel_id
        
        # Default to all items
        available_items = SURVIVORS + KILLERS
        
        # If in an active match, show only valid picks for current player
        if thread_id in matchmaking.active_matches:
            match = matchmaking.active_matches[thread_id]
            user = interaction.user
            
            # Check if it's their turn and in pick phase
            if match.current_phase == "pick" and match.current_turn and match.current_turn.id == user.id:
                # Get the role they need to pick
                required_role = match.get_current_player_role()
                
                # Get available items of that role (not banned, not picked)
                available_items = match.get_available_items(required_role)
                
                # Remove already picked items
                picked_items = match.player1_picks + match.player2_picks
                available_items = [item for item in available_items if item not in picked_items]
        
        # Filter by current input
        if current:
            filtered = [item for item in available_items if current.lower() in item.lower()]
        else:
            filtered = available_items
        
        # Return top 25 matches (Discord limit)
        return [
            app_commands.Choice(name=item, value=item)
            for item in filtered[:25]
        ]
    
    @tree.command(name="iwon", description="Report that you won the round")
    async def i_won(interaction: discord.Interaction):
        await matchmaking.handle_result(interaction, "win")
    
    @tree.command(name="ilose", description="Report that you lost the round")
    async def i_lose(interaction: discord.Interaction):
        await matchmaking.handle_result(interaction, "loss")
    
    @tree.command(name="cancel", description="Cancel the current match (-8 points penalty)")
    async def cancel_match(interaction: discord.Interaction):
        await matchmaking.handle_cancel(interaction)
    
    @tree.command(name="stats", description="View your or another player's stats")
    @app_commands.describe(user="User to check stats for (optional)")
    async def view_stats(interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        stats = matchmaking.get_or_create_stats(target)
        
        embed = discord.Embed(
            title=f"📊 Stats for {target.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Points", value=str(stats.points), inline=True)
        embed.add_field(name="Wins", value=str(stats.wins), inline=True)
        embed.add_field(name="Losses", value=str(stats.losses), inline=True)
        
        if stats.wins + stats.losses > 0:
            winrate = (stats.wins / (stats.wins + stats.losses)) * 100
            embed.add_field(name="Win Rate", value=f"{winrate:.1f}%", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @tree.command(name="leaderboard", description="View top players")
    async def leaderboard(interaction: discord.Interaction):
        sorted_stats = sorted(
            matchmaking.player_stats.values(),
            key=lambda s: s.points,
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="🏆 Leaderboard - Top 10",
            color=discord.Color.gold()
        )
        
        for i, stats in enumerate(sorted_stats, 1):
            embed.add_field(
                name=f"{i}. {stats.username}",
                value=f"Points: {stats.points} | W/L: {stats.wins}/{stats.losses}",
                inline=False
            )
        
        if not sorted_stats:
            embed.description = "No players yet!"
        
        await interaction.response.send_message(embed=embed)
    
    return matchmaking
