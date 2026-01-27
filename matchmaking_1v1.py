"""
TEAM MATCHMAKING SYSTEM - 1v1 MODE
1v1 Matchmaking System integrated with Multi-Mode Stats
Handles matchmaking, ban/pick phases, and point tracking for 1v1 only
"""

import discord
from discord import app_commands
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

# 1v1 Game Constants
MAX_PICKS = 3
MAX_BANS = 2
WIN_POINTS = 15
LOSS_POINTS = -15
CANCEL_PENALTY = -8


class Match1v1:
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
        
        # Match results - Track round wins
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
        Round 1: P1 picks Killer, P2 picks Survivor
        Round 2: P2 picks Killer, P1 picks Survivor
        Round 3: P1 picks Killer, P2 picks Survivor
        """
        if self.current_round == 1:
            return "killer" if self.current_turn == self.player1 else "survivor"
        elif self.current_round == 2:
            return "survivor" if self.current_turn == self.player1 else "killer"
        else:  # Round 3
            return "killer" if self.current_turn == self.player1 else "survivor"


class Matchmaking1v1System:
    """1v1 Matchmaking system integrated with multi-mode stats"""
    def __init__(self, bot_client, multi_mode_stats):
        self.client = bot_client
        self.multi_mode_stats = multi_mode_stats
        self.active_matches: Dict[int, Match1v1] = {}  # thread_id -> Match
        self.waiting_players: Dict[int, Match1v1] = {}  # channel_id -> Match
        self.ALLOWED_CHANNEL_ID = 1465526001110093834
    
    async def start_matchmaking(self, interaction: discord.Interaction):
        """Start looking for a 1v1 match"""
        # Restriction: Only allow matchmaking in specific channel
        if interaction.channel_id != self.ALLOWED_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 1v1 can only be used in <#{self.ALLOWED_CHANNEL_ID}>!",
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
            await self.start_match(existing_match, interaction)
            del self.waiting_players[channel_id]
        else:
            # Create new waiting match
            match = Match1v1(user, interaction.channel)
            self.waiting_players[channel_id] = match
            
            embed = discord.Embed(
                title="Searching for 1v1 Opponent",
                description=f"{user.mention} is looking for a match!",
                color=discord.Color.blue()
            )
            embed.add_field(name="Waiting...", value="Another player can use `/1v1` to join!", inline=False)
            
            await interaction.response.send_message(embed=embed)
            match.waiting_message = await interaction.original_response()
    
    async def start_match(self, match: Match1v1, interaction: discord.Interaction):
        """Start a match between two players"""
        # Delete waiting message
        if match.waiting_message:
            try:
                await match.waiting_message.delete()
            except:
                pass
        
        # Create match announcement
        embed = discord.Embed(
            title="1v1 Match Starting!",
            description=f"{match.player1.mention} vs {match.player2.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Format", value="Best of 3 rounds", inline=False)
        embed.add_field(name="Next Phase", value="Ban Phase - 2 bans each", inline=False)
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Create thread
        thread = await message.create_thread(
            name=f"1v1: {match.player1.display_name} vs {match.player2.display_name}",
            auto_archive_duration=60
        )
        
        match.thread = thread
        self.active_matches[thread.id] = match
        
        # Start ban phase
        await self.start_ban_phase(match)
    
    async def start_ban_phase(self, match: Match1v1):
        """Start the ban phase"""
        match.current_phase = "ban"
        match.current_turn = match.player1
        
        embed = discord.Embed(
            title="BAN PHASE",
            description="Each player bans 2 items (survivors or killers)",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Current Turn",
            value=f"{match.current_turn.mention} - Use `/ban <item>`",
            inline=False
        )
        embed.add_field(
            name="Bans So Far",
            value=f"**{match.player1.display_name}:** {len(match.player1_bans)}/2\n"
                  f"**{match.player2.display_name}:** {len(match.player2_bans)}/2",
            inline=False
        )
        
        match.status_message = await match.thread.send(embed=embed)
    
    async def handle_ban(self, interaction: discord.Interaction, item: str):
        """Handle a ban"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        # Validate item
        all_items = SURVIVORS + KILLERS
        normalized_item = None
        for valid_item in all_items:
            if valid_item.lower().replace(" ", "") == item.lower().replace(" ", ""):
                normalized_item = valid_item
                break
        
        if not normalized_item:
            await interaction.response.send_message(f"❌ Invalid item: {item}", ephemeral=True)
            return
        
        # Check if already banned
        if normalized_item in match.player1_bans + match.player2_bans:
            await interaction.response.send_message(f"❌ {normalized_item} is already banned!", ephemeral=True)
            return
        
        # Add ban
        if user.id == match.player1.id:
            match.player1_bans.append(normalized_item)
        else:
            match.player2_bans.append(normalized_item)
        
        await interaction.response.send_message(f"🚫 Banned **{normalized_item}**!")
        
        # Check if ban phase complete
        if len(match.player1_bans) >= MAX_BANS and len(match.player2_bans) >= MAX_BANS:
            await self.start_pick_phase(match)
        else:
            # Switch turns
            match.current_turn = match.player2 if match.current_turn == match.player1 else match.player1
            await self.update_ban_status(match)
    
    async def update_ban_status(self, match: Match1v1):
        """Update ban phase status"""
        embed = discord.Embed(
            title="BAN PHASE",
            description="Each player bans 2 items",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Current Turn",
            value=f"{match.current_turn.mention} - Use `/ban <item>`",
            inline=False
        )
        
        p1_bans = ", ".join(match.player1_bans) if match.player1_bans else "None yet"
        p2_bans = ", ".join(match.player2_bans) if match.player2_bans else "None yet"
        
        embed.add_field(
            name=f"{match.player1.display_name}'s Bans ({len(match.player1_bans)}/2)",
            value=p1_bans,
            inline=True
        )
        embed.add_field(
            name=f"{match.player2.display_name}'s Bans ({len(match.player2_bans)}/2)",
            value=p2_bans,
            inline=True
        )
        
        await match.status_message.edit(embed=embed)
    
    async def start_pick_phase(self, match: Match1v1):
        """Start pick phase for current round"""
        match.current_phase = "pick"
        match.current_turn = match.player1
        
        embed = discord.Embed(
            title=f"PICK PHASE - Round {match.current_round}/3",
            description="Pick your characters!",
            color=discord.Color.blue()
        )
        
        # Show role assignments
        p1_role = "Killer" if match.current_round != 2 else "Survivor"
        p2_role = "Survivor" if match.current_round != 2 else "Killer"
        
        embed.add_field(name=match.player1.display_name, value=p1_role, inline=True)
        embed.add_field(name=match.player2.display_name, value=p2_role, inline=True)
        embed.add_field(
            name="Current Turn",
            value=f"{match.current_turn.mention} - Use `/pick <item>`",
            inline=False
        )
        
        banned_items = ", ".join(match.player1_bans + match.player2_bans)
        embed.add_field(name="Banned Items", value=banned_items, inline=False)
        
        match.status_message = await match.thread.send(embed=embed)
    
    async def handle_pick(self, interaction: discord.Interaction, item: str):
        """Handle a pick"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        if match.current_phase != "pick":
            await interaction.response.send_message("❌ Not in pick phase!", ephemeral=True)
            return
        
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        # Get required role
        required_role = match.get_current_player_role()
        available_items = match.get_available_items(required_role)
        
        # Validate item
        normalized_item = None
        for valid_item in available_items:
            if valid_item.lower().replace(" ", "") == item.lower().replace(" ", ""):
                normalized_item = valid_item
                break
        
        if not normalized_item:
            role_name = "killer" if required_role == "killer" else "survivor"
            await interaction.response.send_message(
                f"❌ Invalid {role_name}: {item}",
                ephemeral=True
            )
            return
        
        # Check if already picked
        all_picks = match.player1_picks + match.player2_picks
        if normalized_item in all_picks:
            await interaction.response.send_message(f"❌ {normalized_item} already picked!", ephemeral=True)
            return
        
        # Add pick
        if user.id == match.player1.id:
            match.player1_picks.append(normalized_item)
        else:
            match.player2_picks.append(normalized_item)
        
        await interaction.response.send_message(f"✅ Picked **{normalized_item}**!")
        
        # Check if both players picked
        if len(match.player1_picks) > 0 and len(match.player2_picks) > 0:
            await self.start_results_phase(match)
        else:
            # Switch turns
            match.current_turn = match.player2 if match.current_turn == match.player1 else match.player1
            await self.update_pick_status(match)
    
    async def update_pick_status(self, match: Match1v1):
        """Update pick phase status"""
        embed = discord.Embed(
            title=f"PICK PHASE - Round {match.current_round}/3",
            description="Pick your characters!",
            color=discord.Color.blue()
        )
        
        p1_role = "Killer" if match.current_round != 2 else "Survivor"
        p2_role = "Survivor" if match.current_round != 2 else "Killer"
        
        p1_pick = match.player1_picks[-1] if match.player1_picks else "Not picked"
        p2_pick = match.player2_picks[-1] if match.player2_picks else "Not picked"
        
        embed.add_field(
            name=match.player1.display_name,
            value=f"{p1_role}\n**Pick:** {p1_pick}",
            inline=True
        )
        embed.add_field(
            name=match.player2.display_name,
            value=f"{p2_role}\n**Pick:** {p2_pick}",
            inline=True
        )
        embed.add_field(
            name="Current Turn",
            value=f"{match.current_turn.mention}",
            inline=False
        )
        
        await match.status_message.edit(embed=embed)
    
    async def start_results_phase(self, match: Match1v1):
        """Start results phase"""
        match.current_phase = "results"
        
        embed = discord.Embed(
            title=f"ROUND {match.current_round} - Play Now!",
            description="Play the round, then report results",
            color=discord.Color.gold()
        )
        
        p1_role = "Killer" if match.current_round != 2 else "Survivor"
        p2_role = "Survivor" if match.current_round != 2 else "Killer"
        
        embed.add_field(
            name=match.player1.display_name,
            value=f"{p1_role}: **{match.player1_picks[-1]}**",
            inline=True
        )
        embed.add_field(
            name=match.player2.display_name,
            value=f"{p2_role}: **{match.player2_picks[-1]}**",
            inline=True
        )
        embed.add_field(
            name="Report Results",
            value="Use `/iwon` if you won or `/ilose` if you lost",
            inline=False
        )
        embed.add_field(
            name="Current Score",
            value=f"{match.player1.display_name}: {match.player1_score} | {match.player2.display_name}: {match.player2_score}",
            inline=False
        )
        
        await match.thread.send(embed=embed)
    
    async def handle_result(self, interaction: discord.Interaction, claim: str):
        """Handle result reporting"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Not in results phase!", ephemeral=True)
            return
        
        # Record claim
        if user.id == match.player1.id:
            if match.player1_claimed:
                await interaction.response.send_message("❌ You already reported!", ephemeral=True)
                return
            match.player1_claimed = claim
        elif user.id == match.player2.id:
            if match.player2_claimed:
                await interaction.response.send_message("❌ You already reported!", ephemeral=True)
                return
            match.player2_claimed = claim
        else:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        await interaction.response.send_message(f"✅ Recorded: **{claim}**")
        
        # Check if both reported
        if match.player1_claimed and match.player2_claimed:
            await self.process_round_result(match)
    
    async def process_round_result(self, match: Match1v1):
        """Process round results"""
        # Validate claims
        valid = (
            (match.player1_claimed == "win" and match.player2_claimed == "loss") or
            (match.player1_claimed == "loss" and match.player2_claimed == "win")
        )
        
        if not valid:
            await match.thread.send(
                "❌ Results don't match! Please report again correctly."
            )
            match.player1_claimed = None
            match.player2_claimed = None
            return
        
        # Update scores
        if match.player1_claimed == "win":
            match.player1_score += 1
        else:
            match.player2_score += 1
        
        match.rounds_completed += 1
        
        # Check if match is over
        if match.player1_score >= 2 or match.player2_score >= 2 or match.rounds_completed >= 3:
            await self.end_match(match)
        else:
            # Next round
            match.current_round += 1
            match.player1_claimed = None
            match.player2_claimed = None
            
            await match.thread.send(
                f"✅ Round {match.rounds_completed} complete!\n"
                f"**Score:** {match.player1.display_name} {match.player1_score} - {match.player2_score} {match.player2.display_name}\n"
                f"Starting Round {match.current_round}..."
            )
            
            await self.start_pick_phase(match)
    
    async def end_match(self, match: Match1v1):
        """End the match and award points"""
        match.match_complete = True
        
        # Determine winner
        if match.player1_score > match.player2_score:
            winner = match.player1
            loser = match.player2
        else:
            winner = match.player2
            loser = match.player1
        
        # Update stats using multi-mode stats system
        winner_stats = self.multi_mode_stats.get_or_create_stats(winner, "1v1")
        winner_stats.points += WIN_POINTS
        winner_stats.wins += 1
        
        loser_stats = self.multi_mode_stats.get_or_create_stats(loser, "1v1")
        loser_stats.points = max(0, loser_stats.points + LOSS_POINTS)
        loser_stats.losses += 1
        
        self.multi_mode_stats.save_stats()
        
        # Create final embed
        embed = discord.Embed(
            title="MATCH COMPLETE!",
            description=f"**{winner.mention}** wins!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Final Score",
            value=f"{match.player1.display_name}: {match.player1_score}\n{match.player2.display_name}: {match.player2_score}",
            inline=False
        )
        embed.add_field(
            name="Points",
            value=f"{winner.mention}: +{WIN_POINTS}\n{loser.mention}: {LOSS_POINTS}",
            inline=False
        )
        
        await match.thread.send(embed=embed)
        
        # Clean up
        del self.active_matches[match.thread.id]
        await match.thread.edit(archived=True)
    
    async def handle_cancel(self, interaction: discord.Interaction):
        """Handle match cancellation"""
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        # Must be a player in the match
        if user.id not in [match.player1.id, match.player2.id]:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        # Apply penalty to both players
        p1_stats = self.multi_mode_stats.get_or_create_stats(match.player1, "1v1")
        p1_stats.points = max(0, p1_stats.points + CANCEL_PENALTY)
        
        p2_stats = self.multi_mode_stats.get_or_create_stats(match.player2, "1v1")
        p2_stats.points = max(0, p2_stats.points + CANCEL_PENALTY)
        
        self.multi_mode_stats.save_stats()
        
        embed = discord.Embed(
            title="❌ Match Cancelled",
            description=f"Match cancelled by {user.mention}",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Penalty",
            value=f"Both players: {CANCEL_PENALTY} points",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Clean up
        del self.active_matches[thread_id]
        await match.thread.edit(archived=True)


def setup_1v1_commands(tree: app_commands.CommandTree, matchmaking_1v1: Matchmaking1v1System):
    """Setup 1v1 matchmaking commands"""
    
    @tree.command(name="1v1", description="Start or join a 1v1 match")
    async def start_1v1(interaction: discord.Interaction):
        await matchmaking_1v1.start_matchmaking(interaction)
    
    @tree.command(name="ban", description="Ban an item during ban phase")
    @app_commands.describe(item="Item to ban")
    async def ban_item(interaction: discord.Interaction, item: str):
        await matchmaking_1v1.handle_ban(interaction, item)
    
    @ban_item.autocomplete('item')
    async def ban_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for ban command"""
        thread_id = interaction.channel_id
        all_items = SURVIVORS + KILLERS
        
        if thread_id in matchmaking_1v1.active_matches:
            match = matchmaking_1v1.active_matches[thread_id]
            banned_items = match.player1_bans + match.player2_bans
            all_items = [item for item in all_items if item not in banned_items]
        
        if current:
            filtered = [item for item in all_items if current.lower() in item.lower()]
        else:
            filtered = all_items
        
        return [app_commands.Choice(name=item, value=item) for item in filtered[:25]]
    
    @tree.command(name="pick", description="Pick an item during pick phase")
    @app_commands.describe(item="Item to pick")
    async def pick_item(interaction: discord.Interaction, item: str):
        await matchmaking_1v1.handle_pick(interaction, item)
    
    @pick_item.autocomplete('item')
    async def pick_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for pick command"""
        thread_id = interaction.channel_id
        available_items = SURVIVORS + KILLERS
        
        if thread_id in matchmaking_1v1.active_matches:
            match = matchmaking_1v1.active_matches[thread_id]
            user = interaction.user
            
            if match.current_phase == "pick" and match.current_turn and match.current_turn.id == user.id:
                required_role = match.get_current_player_role()
                available_items = match.get_available_items(required_role)
                picked_items = match.player1_picks + match.player2_picks
                available_items = [item for item in available_items if item not in picked_items]
        
        if current:
            filtered = [item for item in available_items if current.lower() in item.lower()]
        else:
            filtered = available_items
        
        return [app_commands.Choice(name=item, value=item) for item in filtered[:25]]
    
    @tree.command(name="iwon", description="Report that you won the round")
    async def i_won(interaction: discord.Interaction):
        await matchmaking_1v1.handle_result(interaction, "win")
    
    @tree.command(name="ilose", description="Report that you lost the round")
    async def i_lose(interaction: discord.Interaction):
        await matchmaking_1v1.handle_result(interaction, "loss")
    
    @tree.command(name="cancel", description="Cancel the current match (-8 points penalty)")
    async def cancel_match(interaction: discord.Interaction):
        await matchmaking_1v1.handle_cancel(interaction)
    
    return matchmaking_1v1
