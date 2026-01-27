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
        if self.current_round == 1:
            return "killer" if self.current_turn == self.player1 else "survivor"
        elif self.current_round == 2:
            return "survivor" if self.current_turn == self.player1 else "killer"
        else:
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
            title="BAN & PICK PHASE",
            color=discord.Color.gold()
        )
        
        if match.current_phase == "ban":
            phase_text = "BAN PHASE"
        elif match.current_phase == "pick":
            phase_text = f"PICK PHASE - Round {match.current_round}"
        else:
            phase_text = f"RESULTS - Round {match.rounds_completed + 1}"
        
        embed.description = f"**Current Phase:** {phase_text}\n"
        
        if match.rounds_completed > 0 or match.current_phase == "results":
            embed.description += f"**Score:** {match.player1_score}-{match.player2_score}\n"
        
        if match.current_turn and match.current_phase != "results":
            role = match.get_current_player_role() if match.current_phase == "pick" else None
            turn_text = f"**Turn:** {match.current_turn.mention}"
            if role:
                turn_text += f" (Picking {role.upper()})"
            embed.description += turn_text
        
        p1_bans_text = ", ".join(match.player1_bans) if match.player1_bans else "None"
        p2_bans_text = ", ".join(match.player2_bans) if match.player2_bans else "None"
        
        embed.add_field(
            name="🚫 Bans",
            value=f"**Player 1:** {p1_bans_text} ({len(match.player1_bans)}/{MAX_BANS})\n"
                  f"**Player 2:** {p2_bans_text} ({len(match.player2_bans)}/{MAX_BANS})",
            inline=False
        )
        
        p1_picks_text = ", ".join(match.player1_picks) if match.player1_picks else "None"
        p2_picks_text = ", ".join(match.player2_picks) if match.player2_picks else "None"
        
        embed.add_field(
            name="✅ Picks",
            value=f"**Player 1:** {p1_picks_text} ({len(match.player1_picks)}/{MAX_PICKS})\n"
                  f"**Player 2:** {p2_picks_text} ({len(match.player2_picks)}/{MAX_PICKS})",
            inline=False
        )
        
        if match.current_phase == "pick" and match.current_turn:
            role = match.get_current_player_role()
            available = match.get_available_items(role)
            if available:
                items_list = "\n".join([f"• {item}" for item in available[:10]])
                if len(available) > 10:
                    items_list += f"\n... and {len(available) - 10} more"
                embed.add_field(
                    name=f"Available {role.capitalize()}s",
                    value=f"```\n{items_list}\n```",
                    inline=False
                )
        
        return embed
    
    async def handle_ban(self, interaction: discord.Interaction, item: str):
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
        
        is_player1 = user.id == match.player1.id
        player_bans = match.player1_bans if is_player1 else match.player2_bans
        
        if len(player_bans) >= MAX_BANS:
            await interaction.response.send_message(f"❌ You've already banned {MAX_BANS} items!", ephemeral=True)
            return
        
        normalized_input = item.lower().replace(" ", "")
        
        all_items = SURVIVORS + KILLERS
        matched_item = None
        for valid_item in all_items:
            if valid_item.lower().replace(" ", "") == normalized_input:
                matched_item = valid_item
                break
        
        if not matched_item:
            await interaction.response.send_message(f"❌ Invalid item: {item}", ephemeral=True)
            return
        
        if matched_item in match.player1_bans or matched_item in match.player2_bans:
            await interaction.response.send_message(f"❌ {matched_item} is already banned!", ephemeral=True)
            return
        
        player_bans.append(matched_item)
        
        player_label = "Player 1" if is_player1 else "Player 2"
        await interaction.response.send_message(
            f"🚫 **{player_label}** ({user.mention}) banned **{matched_item}**!",
            ephemeral=False
        )
        
        if len(match.player1_bans) == MAX_BANS and len(match.player2_bans) == MAX_BANS:
            match.current_phase = "pick"
            match.current_round = 1
            match.current_turn = match.player1
            await match.thread.send("✅ **BAN PHASE COMPLETE!** Starting **PICK PHASE - Round 1**...")
        else:
            match.current_turn = match.player2 if is_player1 else match.player1
        
        await self.update_status_message(match)
    
    async def handle_pick(self, interaction: discord.Interaction, item: str):
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
        
        is_player1 = user.id == match.player1.id
        player_picks = match.player1_picks if is_player1 else match.player2_picks
        
        required_role = match.get_current_player_role()
        item_pool = KILLERS if required_role == "killer" else SURVIVORS
        
        normalized_input = item.lower().replace(" ", "")
        
        matched_item = None
        for valid_item in item_pool:
            if valid_item.lower().replace(" ", "") == normalized_input:
                matched_item = valid_item
                break
        
        if not matched_item:
            await interaction.response.send_message(
                f"❌ You must pick a **{required_role}**! {item} is not valid.",
                ephemeral=True
            )
            return
        
        if matched_item in match.player1_bans or matched_item in match.player2_bans:
            await interaction.response.send_message(f"❌ {matched_item} is banned!", ephemeral=True)
            return
        
        if matched_item in match.player1_picks or matched_item in match.player2_picks:
            await interaction.response.send_message(f"❌ {matched_item} is already picked!", ephemeral=True)
            return
        
        player_picks.append(matched_item)
        
        player_label = "Player 1" if is_player1 else "Player 2"
        await interaction.response.send_message(
            f"✅ **{player_label}** ({user.mention}) picked **{matched_item}** ({required_role.capitalize()})!",
            ephemeral=False
        )
        
        total_picks = len(match.player1_picks) + len(match.player2_picks)
        
        if total_picks == 6:
            match.current_phase = "results"
            await match.thread.send(
                "✅ **PICK PHASE COMPLETE!**\n"
                f"**Current Score:** {match.player1_score}-{match.player2_score}\n"
                f"Play **Round {match.rounds_completed + 1}** and use `/iwon` or `/ilose` to report the result!"
            )
            await self.update_status_message(match)
        elif total_picks % 2 == 0:
            match.current_round += 1
            match.current_turn = match.player2 if match.current_round == 2 else match.player1
            await match.thread.send(f"✅ **Round {match.current_round} starting...**")
            await self.update_status_message(match)
        else:
            match.current_turn = match.player2 if is_player1 else match.player1
            await self.update_status_message(match)
    
    async def handle_result(self, interaction: discord.Interaction, result: str):
        thread_id = interaction.channel_id
        
        if thread_id not in self.active_matches:
            await interaction.response.send_message("❌ No active match in this thread!", ephemeral=True)
            return
        
        match = self.active_matches[thread_id]
        user = interaction.user
        
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Complete the pick phase first!", ephemeral=True)
            return
        
        is_player1 = user.id == match.player1.id
        is_player2 = user.id == match.player2.id
        
        if not (is_player1 or is_player2):
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
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
        
        if match.player1_claimed and match.player2_claimed:
            valid = (
                (match.player1_claimed == "win" and match.player2_claimed == "loss") or
                (match.player1_claimed == "loss" and match.player2_claimed == "win")
            )
            
            if not valid:
                await interaction.response.send_message(
                    "❌ **Results don't match!** Please verify who won this round.",
                    ephemeral=False
                )
                match.player1_claimed = None
                match.player2_claimed = None
                return
            
            round_winner = match.player1 if match.player1_claimed == "win" else match.player2
            is_p1_winner = round_winner == match.player1
            
            if is_p1_winner:
                match.player1_score += 1
            else:
                match.player2_score += 1
            
            match.rounds_completed += 1
            
            match_over = (match.player1_score == 2 or match.player2_score == 2 or match.rounds_completed == 3)
            
            if match_over:
                if match.player1_score > match.player2_score:
                    winner = match.player1
                    loser = match.player2
                else:
                    winner = match.player2
                    loser = match.player1
                
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
                
                await match.thread.edit(auto_archive_duration=5)
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
    
    return matchmaking_1v1
