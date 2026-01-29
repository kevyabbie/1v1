"""
1v1 Matchmaking System - Integrated with Multi-Mode Stats
Uses the old proven matchmaking mechanism
"""
import discord
from discord import app_commands
from typing import Optional, Dict, List
from datetime import datetime

SURVIVORS = [
    "Noob", "Guest 1337", "Shedletsky", "Chance", "Two Time",
    "Veeronica", "Elliot", "007n7", "Dusekkar", "Builderman", "Taph"
]

KILLERS = [
    "Noli", "Guest 666", "John Doe", "Slasher", 
    "1x1x1x1", "C00lkidd", "Nosferatu"
]

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
        
        self.current_round = 1
        self.current_phase = "ban"
        self.current_turn: Optional[discord.Member] = None
        
        self.player1_bans: List[str] = []
        self.player2_bans: List[str] = []
        self.player1_picks: List[str] = []
        self.player2_picks: List[str] = []
        
        self.player1_score = 0
        self.player2_score = 0
        self.rounds_completed = 0
        self.player1_claimed: Optional[str] = None
        self.player2_claimed: Optional[str] = None
        self.match_complete = False
        
        self.status_message: Optional[discord.Message] = None
    
    def get_available_items(self, item_type: str) -> List[str]:
        all_items = SURVIVORS if item_type == "survivor" else KILLERS
        banned = self.player1_bans + self.player2_bans
        return [item for item in all_items if item not in banned]
    
    def get_current_player_role(self) -> str:
        """Get current player's role (killer or survivor)
        Round 1: Player1 killer, Player2 survivor
        Round 2: Player1 survivor, Player2 killer
        Round 3: Player1 killer, Player2 survivor
        """
        if self.current_round == 1:
            # Round 1: player1 is killer
            return "killer" if self.current_turn == self.player1 else "survivor"
        elif self.current_round == 2:
            # Round 2: player2 is killer (swap roles)
            return "survivor" if self.current_turn == self.player1 else "killer"
        else:  # Round 3
            # Round 3: player1 is killer again
            return "killer" if self.current_turn == self.player1 else "survivor"


class Matchmaking1v1System:
    """1v1 Matchmaking using multi-mode stats"""
    def __init__(self, bot_client, multi_mode_stats):
        self.client = bot_client
        self.multi_mode_stats = multi_mode_stats
        self.active_matches: Dict[int, Match1v1] = {}
        self.waiting_players: Dict[int, Match1v1] = {}
        self.ALLOWED_CHANNEL_ID = 1465526001110093834
    
    async def start_matchmaking(self, interaction: discord.Interaction):
        if interaction.channel_id != self.ALLOWED_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 1v1 can only be used in <#{self.ALLOWED_CHANNEL_ID}>!",
                ephemeral=True
            )
            return
        
        channel_id = interaction.channel_id
        user = interaction.user
        
        for match in self.active_matches.values():
            if match.player1.id == user.id or (match.player2 and match.player2.id == user.id):
                await interaction.response.send_message(
                    "❌ You're already in an active match!", 
                    ephemeral=True
                )
                return
        
        if channel_id in self.waiting_players:
            existing_match = self.waiting_players[channel_id]
            
            if existing_match.player1.id == user.id:
                await interaction.response.send_message(
                    "❌ You're already waiting for an opponent!", 
                    ephemeral=True
                )
                return
            
            existing_match.player2 = user
            del self.waiting_players[channel_id]
            
            await existing_match.waiting_message.edit(
                embed=self.create_match_found_embed(existing_match)
            )
            
            thread = await existing_match.waiting_message.create_thread(
                name=f"1v1: {existing_match.player1.display_name} vs {existing_match.player2.display_name}",
                auto_archive_duration=60
            )
            existing_match.thread = thread
            
            self.active_matches[thread.id] = existing_match
            
            await self.start_ban_pick_phase(existing_match)
            
            await interaction.response.send_message(
                f"✅ Match found! Check the thread: {thread.mention}",
                ephemeral=True
            )
        
        else:
            match = Match1v1(user, interaction.channel)
            
            embed = self.create_waiting_embed(match)
            await interaction.response.send_message(embed=embed)
            
            message = await interaction.original_response()
            match.waiting_message = message
            
            self.waiting_players[channel_id] = match
    
    def create_waiting_embed(self, match: Match1v1) -> discord.Embed:
        embed = discord.Embed(
            title="Searching for 1v1 Opponent",
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
            value="Type `/findmatch` to accept the challenge!",
            inline=False
        )
        return embed
    
    def create_match_found_embed(self, match: Match1v1) -> discord.Embed:
        embed = discord.Embed(
            title="Match Found!",
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
    
    async def start_ban_pick_phase(self, match: Match1v1):
        thread = match.thread
        
        await thread.send(
            f"Welcome {match.player1.mention} and {match.player2.mention}!\n"
            f"**Player 1:** {match.player1.display_name}\n"
            f"**Player 2:** {match.player2.display_name}\n\n"
            f"Starting **BAN PHASE**..."
        )
        
        match.current_turn = match.player1
        match.current_phase = "ban"
        
        await self.update_status_message(match)
    
    async def update_status_message(self, match: Match1v1):
        embed = self.create_status_embed(match)
        
        if match.status_message:
            await match.status_message.edit(embed=embed)
        else:
            match.status_message = await match.thread.send(embed=embed)
    
    def create_status_embed(self, match: Match1v1) -> discord.Embed:
        embed = discord.Embed(
            title="Match Status",
            color=discord.Color.blue()
        )
        
        score_text = f"**Score:** {match.player1_score}-{match.player2_score}"
        round_text = f"**Round:** {match.current_round}/3"
        embed.description = f"{score_text} | {round_text}"
        
        if match.current_phase == "ban":
            embed.add_field(
                name="🚫 BAN PHASE",
                value=f"**Current Turn:** {match.current_turn.mention if match.current_turn else 'Unknown'}\n"
                      f"**Bans Left:** {MAX_BANS - len(match.player1_bans if match.current_turn == match.player1 else match.player2_bans)}/{MAX_BANS}",
                inline=False
            )
        
        elif match.current_phase == "pick":
            role = match.get_current_player_role() if match.current_turn else "unknown"
            picks_count = len(match.player1_picks if match.current_turn == match.player1 else match.player2_picks)
            
            embed.add_field(
                name="🎯 PICK PHASE",
                value=f"**Current Turn:** {match.current_turn.mention if match.current_turn else 'Unknown'}\n"
                      f"**Role:** {role.upper()}\n"
                      f"**Picks:** {picks_count}/{MAX_PICKS}",
                inline=False
            )
        
        elif match.current_phase == "results":
            embed.add_field(
                name="📊 ROUND RESULTS",
                value=f"Play Round {match.rounds_completed + 1} and use `/iwon` or `/ilose` to report results!",
                inline=False
            )
        
        if match.player1_bans or match.player2_bans:
            bans_text = ""
            if match.player1_bans:
                bans_text += f"**{match.player1.display_name}:** {', '.join(match.player1_bans)}\n"
            if match.player2_bans:
                bans_text += f"**{match.player2.display_name}:** {', '.join(match.player2_bans)}"
            
            if bans_text:
                embed.add_field(
                    name="Banned Items",
                    value=bans_text,
                    inline=False
                )
        
        if match.player1_picks or match.player2_picks:
            picks_text = ""
            if match.player1_picks:
                picks_text += f"**{match.player1.display_name}:** {', '.join(match.player1_picks)}\n"
            if match.player2_picks:
                picks_text += f"**{match.player2.display_name}:** {', '.join(match.player2_picks)}"
            
            if picks_text:
                embed.add_field(
                    name="Current Picks",
                    value=picks_text,
                    inline=False
                )
        
        return embed
    
    async def handle_ban(self, interaction: discord.Interaction, item: str):
        thread_id = interaction.channel_id
        user = interaction.user
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        is_player1 = user.id == match.player1.id
        player_bans = match.player1_bans if is_player1 else match.player2_bans
        
        if len(player_bans) >= MAX_BANS:
            await interaction.response.send_message("❌ You've used all your bans!", ephemeral=True)
            return
        
        all_items = SURVIVORS + KILLERS
        if item not in all_items:
            await interaction.response.send_message(f"❌ Invalid item: {item}", ephemeral=True)
            return
        
        if item in match.player1_bans or item in match.player2_bans:
            await interaction.response.send_message(f"❌ {item} is already banned!", ephemeral=True)
            return
        
        player_bans.append(item)
        
        await interaction.response.send_message(
            f"✅ **{user.display_name}** banned **{item}**! ({len(player_bans)}/{MAX_BANS})",
            ephemeral=False
        )
        
        total_bans = len(match.player1_bans) + len(match.player2_bans)
        if total_bans >= MAX_BANS * 2:
            match.current_phase = "pick"
            match.current_turn = match.player1
            match.current_round = 1
            
            await match.thread.send(
                f"🎯 **PICK PHASE**\n"
                f"**Round 1** - {match.player1.mention} is the **KILLER** and picks first!\n"
                f"Use `/pick <item>` to select your characters."
            )
        else:
            match.current_turn = match.player2 if is_player1 else match.player1
        
        await self.update_status_message(match)
    
    async def handle_pick(self, interaction: discord.Interaction, item: str):
        thread_id = interaction.channel_id
        user = interaction.user
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        
        if match.current_phase != "pick":
            await interaction.response.send_message("❌ Not in pick phase!", ephemeral=True)
            return
        
        if match.current_turn.id != user.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        
        is_player1 = user.id == match.player1.id
        player_picks = match.player1_picks if is_player1 else match.player2_picks
        
        if len(player_picks) >= MAX_PICKS:
            await interaction.response.send_message("❌ You've used all your picks!", ephemeral=True)
            return
        
        required_role = match.get_current_player_role()
        available_items = match.get_available_items(required_role)
        
        if item not in available_items:
            await interaction.response.send_message(
                f"❌ Invalid pick! You must pick a {required_role.upper()} that hasn't been banned or picked.",
                ephemeral=True
            )
            return
        
        all_picks = match.player1_picks + match.player2_picks
        if item in all_picks:
            await interaction.response.send_message(f"❌ {item} has already been picked!", ephemeral=True)
            return
        
        player_picks.append(item)
        
        await interaction.response.send_message(
            f"✅ **{user.display_name}** picked **{item}**! ({len(player_picks)}/{MAX_PICKS})",
            ephemeral=False
        )
        
        total_picks = len(match.player1_picks) + len(match.player2_picks)
        if total_picks >= MAX_PICKS * 2:
            match.current_phase = "results"
            match.current_turn = None
            
            await match.thread.send(
                f"**Score: {match.player1_score}-{match.player2_score} | Round: {match.current_round}/3**\n\n"
                f"🎮 **ROUND RESULTS**\n"
                f"Play Round {match.current_round} and use `/iwon` or `/ilose` to report results!\n\n"
                f"**Banned Items**\n"
                f"**{match.player1.display_name}:** {', '.join(match.player1_bans) if match.player1_bans else 'None'}\n"
                f"**{match.player2.display_name}:** {', '.join(match.player2_bans) if match.player2_bans else 'None'}\n\n"
                f"**Current Picks**\n"
                f"**{match.player1.display_name}:** {', '.join(match.player1_picks)}\n"
                f"**{match.player2.display_name}:** {', '.join(match.player2_picks)}"
            )
        else:
            match.current_turn = match.player2 if is_player1 else match.player1
        
        await self.update_status_message(match)
    
    async def handle_result(self, interaction: discord.Interaction, result: str):
        thread_id = interaction.channel_id
        user = interaction.user
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Complete the pick phase first!", ephemeral=True)
            return
        
        is_player1 = user.id == match.player1.id
        is_player2 = user.id == match.player2.id
        
        if not is_player1 and not is_player2:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        if is_player1:
            if match.player1_claimed:
                await interaction.response.send_message("❌ You already submitted a result!", ephemeral=True)
                return
            match.player1_claimed = result
        else:
            if match.player2_claimed:
                await interaction.response.send_message("❌ You already submitted a result!", ephemeral=True)
                return
            match.player2_claimed = result
        
        if match.player1_claimed and match.player2_claimed:
            valid_result = (
                (match.player1_claimed == "win" and match.player2_claimed == "loss") or
                (match.player1_claimed == "loss" and match.player2_claimed == "win")
            )
            
            if not valid_result:
                await interaction.response.send_message(
                    "⚠️ **Results don't match!** Please verify who won this round.",
                    ephemeral=False
                )
                match.player1_claimed = None
                match.player2_claimed = None
                return
            
            round_winner = match.player1 if match.player1_claimed == "win" else match.player2
            
            if round_winner.id == match.player1.id:
                match.player1_score += 1
            else:
                match.player2_score += 1
            
            match.rounds_completed += 1
            
            if match.rounds_completed >= 3:
                winner = match.player1 if match.player1_score > match.player2_score else match.player2
                loser = match.player2 if winner.id == match.player1.id else match.player1
                
                winner_stats = self.multi_mode_stats.get_or_create_stats(winner, "1v1")
                loser_stats = self.multi_mode_stats.get_or_create_stats(loser, "1v1")
                
                winner_stats.points += WIN_POINTS
                winner_stats.wins += 1
                loser_stats.points = max(0, loser_stats.points + LOSS_POINTS)
                loser_stats.losses += 1
                
                self.multi_mode_stats.save_stats()
                
                embed = discord.Embed(
                    title="MATCH COMPLETE!",
                    description=f"**{winner.display_name}** wins against **{loser.display_name}**!",
                    color=discord.Color.gold()
                )
                embed.add_field(
                    name="Final Score",
                    value=f"```\n{match.player1_score}-{match.player2_score}\n```",
                    inline=False
                )
                
                embed.add_field(
                    name="Points",
                    value=f"**{winner.display_name}:** +{WIN_POINTS} points (Total: {winner_stats.points})\n"
                          f"**{loser.display_name}:** {LOSS_POINTS} points (Total: {loser_stats.points})",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                match.match_complete = True
                del self.active_matches[thread_id]
                
                # FIXED: Use valid auto_archive_duration value (60 minutes instead of 5)
                await match.thread.edit(archived=True)
            else:
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
                
                match.player1_claimed = None
                match.player2_claimed = None
                
                await self.update_status_message(match)
        
        else:
            waiting_for = match.player2 if is_player1 else match.player1
            current_score = f"{match.player1_score}-{match.player2_score}"
            await interaction.response.send_message(
                f"✅ You claimed a **{result}** for Round {match.rounds_completed + 1}.\n"
                f"**Current Score:** {current_score}\n"
                f"Waiting for {waiting_for.mention} to submit their result.",
                ephemeral=False
            )
    
    async def handle_cancel(self, interaction: discord.Interaction):
        thread_id = interaction.channel_id
        user = interaction.user
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        
        if user.id != match.player1.id and user.id != match.player2.id:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        canceller = match.player1 if user.id == match.player1.id else match.player2
        other_player = match.player2 if user.id == match.player1.id else match.player1
        
        canceller_stats = self.multi_mode_stats.get_or_create_stats(canceller, "1v1")
        canceller_stats.points = max(0, canceller_stats.points + CANCEL_PENALTY)
        self.multi_mode_stats.save_stats()
        
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
        
        del self.active_matches[thread_id]
        await match.thread.edit(archived=True)
    
    async def cancel_waiting(self, interaction: discord.Interaction):
        """Cancel waiting for a 1v1 match"""
        channel_id = interaction.channel_id
        user = interaction.user
        
        # Check if user is waiting in this channel
        if channel_id in self.waiting_players:
            match = self.waiting_players[channel_id]
            if match.player1.id == user.id:
                # Delete the waiting match
                del self.waiting_players[channel_id]
                
                # Delete or edit the waiting message
                try:
                    await match.waiting_message.delete()
                except:
                    pass
                
                await interaction.response.send_message(
                    "✅ Cancelled 1v1 matchmaking.",
                    ephemeral=True
                )
                return
        
        # Not in queue
        await interaction.response.send_message(
            "❌ You're not waiting for a 1v1 match in this channel!",
            ephemeral=True
        )


def setup_1v1_commands(tree: app_commands.CommandTree, matchmaking_1v1: Matchmaking1v1System):
    
    @tree.command(name="findmatch", description="Start or join a 1v1 match")
    async def start_1v1(interaction: discord.Interaction):
        await matchmaking_1v1.start_matchmaking(interaction)
    
    @tree.command(name="ban", description="Ban an item during ban phase")
    @app_commands.describe(item="Item to ban")
    async def ban_item(interaction: discord.Interaction, item: str):
        await matchmaking_1v1.handle_ban(interaction, item)
    
    @ban_item.autocomplete('item')
    async def ban_autocomplete(interaction: discord.Interaction, current: str):
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
    
    @tree.command(name="cancel1v1", description="Cancel 1v1 matchmaking search (no penalty)")
    async def cancel_1v1_search(interaction: discord.Interaction):
        await matchmaking_1v1.cancel_waiting(interaction)
    
    return matchmaking_1v1
