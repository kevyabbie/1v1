================================================================================
# FILE: matchmaking_1v1.py (733 lines)
================================================================================
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
 self.current_phase = "ban" # "ban", "pick", or "results"
 self.current_turn: Optional[discord.Member] = None

 # Bans and Picks (player_id -> list)
 self.player1_bans: List[str] = []
 self.player2_bans: List[str] = []
 self.player1_picks: List[str] = []
 self.player2_picks: List[str] = []

 # Match results - UPDATED TO TRACK ROUND WINS
 self.player1_score = 0 # Track actual round wins
 self.player2_score = 0
 self.rounds_completed = 0 # How many rounds have been fully reported
 self.player1_claimed: Optional[str] = None # "win" or "loss" for current round
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
 else: # Round 3
 # Round 3: P1 = Killer, P2 = Survivor
 return "killer" if self.current_turn == self.player1 else "survivor"
class MatchmakingSystem:
 """Main matchmaking system"""
 def __init__(self, bot_client):
 self.client = bot_client
 self.active_matches: Dict[int, Match] = {} # channel_id -> Match
 self.waiting_players: Dict[int, Match] = {} # channel_id -> Match
 self.player_stats: Dict[int, PlayerStats] = {} # user_id -> PlayerStats
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

 # AUTO-FIX: Fix any negative points on load
 fixed_count = 0
 for stats in self.player_stats.values():
 if stats.points < 0:
 print(f"Auto-fixing negative points for {stats.username}: {stats.points} → 0")
 stats.points = 0
 fixed_count += 1

 if fixed_count > 0:
 print(f"■ Auto-fixed {fixed_count} player(s) with negative points")
 self.save_stats() # Save the corrected data

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
 f"■ Matchmaking can only be used in <#{ALLOWED_CHANNEL_ID}>!",
 ephemeral=True
 )
 return

 channel_id = interaction.channel_id
 user = interaction.user

 # Check if player already in a match
 for match in self.active_matches.values():
 if match.player1.id == user.id or (match.player2 and match.player2.id == user.id):
 await interaction.response.send_message(
 "■ You're already in an active match!",
 ephemeral=True
 )
 return

 # Check if someone is waiting
 if channel_id in self.waiting_players:
 existing_match = self.waiting_players[channel_id]

 # Can't match with yourself
 if existing_match.player1.id == user.id:
 await interaction.response.send_message(
 "■ You're already waiting for an opponent!",
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
 name=f"■ {existing_match.player1.display_name} vs {existing_match.player2.display_name}",
 auto_archive_duration=60
 )
 existing_match.thread = thread

 # Move to active matches
 self.active_matches[thread.id] = existing_match

 # Start ban phase
 await self.start_ban_pick_phase(existing_match)

 await interaction.response.send_message(
 f"■ Match found! Check the thread: {thread.mention}",
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
 title="■ 1v1 Matchmaking",
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
 title="■ Match Found!",
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
 title="■ BAN & PICK PHASE",
 color=discord.Color.gold()
 )

 # Show current phase
 if match.current_phase == "ban":
 phase_text = "BAN PHASE"
 elif match.current_phase == "pick":
 phase_text = f"PICK PHASE - Round {match.current_round}"
 else: # results
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
 name="■ Bans",
 value=f"**Player 1:** {p1_bans_text} ({len(match.player1_bans)}/{MAX_BANS})\n"
 f"**Player 2:** {p2_bans_text} ({len(match.player2_bans)}/{MAX_BANS})",
 inline=False
 )

 # Picks
 p1_picks_text = ", ".join(match.player1_picks) if match.player1_picks else "None"
 p2_picks_text = ", ".join(match.player2_picks) if match.player2_picks else "None"

 embed.add_field(
 name="■ Picks",
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
 name=f"■ Available {role.capitalize()}s",
 value=f"```\n{items_list}\n```",
 inline=False
 )

 return embed

 async def handle_ban(self, interaction: discord.Interaction, item: str):
 """Handle ban command"""
 thread_id = interaction.channel_id

 if thread_id not in self.active_matches:
 await interaction.response.send_message("■ No active match in this thread!", ephemeral=True)
 return

 match = self.active_matches[thread_id]
 user = interaction.user

 # Check if it's ban phase
 if match.current_phase != "ban":
 await interaction.response.send_message("■ Not in ban phase!", ephemeral=True)
 return

 # Check if it's player's turn
 if match.current_turn.id != user.id:
 await interaction.response.send_message("■ Not your turn!", ephemeral=True)
 return

 # Determine which player
 is_player1 = user.id == match.player1.id
 player_bans = match.player1_bans if is_player1 else match.player2_bans

 # Check ban limit
 if len(player_bans) >= MAX_BANS:
 await interaction.response.send_message(f"■ You've already banned {MAX_BANS} items!", ephemeral=True)
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
 await interaction.response.send_message(f"■ Invalid item: {item}", ephemeral=True)
 return

 # Check if already banned
 if matched_item in match.player1_bans or matched_item in match.player2_bans:
 await interaction.response.send_message(f"■ {matched_item} is already banned!", ephemeral=True)
 return

 # Add ban (using the properly formatted name)
 player_bans.append(matched_item)

 # Announce the ban publicly in the thread
 player_label = "Player 1" if is_player1 else "Player 2"
 await interaction.response.send_message(
 f"■ **{player_label}** ({user.mention}) banned **{matched_item}**!",
 ephemeral=False
 )

 # Check if both players finished banning
 if len(match.player1_bans) == MAX_BANS and len(match.player2_bans) == MAX_BANS:
 # Move to pick phase
 match.current_phase = "pick"
 match.current_round = 1
 match.current_turn = match.player1
 await match.thread.send("■ **BAN PHASE COMPLETE!** Starting **PICK PHASE - Round 1**...")
 else:
 # Switch turn
 match.current_turn = match.player2 if is_player1 else match.player1

 await self.update_status_message(match)

 async def handle_pick(self, interaction: discord.Interaction, item: str):
 """Handle pick command"""
 thread_id = interaction.channel_id

 if thread_id not in self.active_matches:
 await interaction.response.send_message("■ No active match in this thread!", ephemeral=True)
 return

 match = self.active_matches[thread_id]
 user = interaction.user

 # Check if it's pick phase
 if match.current_phase != "pick":
 await interaction.response.send_message("■ Not in pick phase!", ephemeral=True)
 return

 # Check if it's player's turn
 if match.current_turn.id != user.id:
 await interaction.response.send_message("■ Not your turn!", ephemeral=True)
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
 f"■ You must pick a **{required_role}**! {item} is not valid.",
 ephemeral=True
 )
 return

 # Check if banned
 if matched_item in match.player1_bans or matched_item in match.player2_bans:
 await interaction.response.send_message(f"■ {matched_item} is banned!", ephemeral=True)
 return

 # Check if already picked
 if matched_item in match.player1_picks or matched_item in match.player2_picks:
 await interaction.response.send_message(f"■ {matched_item} is already picked!", ephemeral=True)
 return

 # Add pick (using the properly formatted name)
 player_picks.append(matched_item)

 # Announce the pick publicly in the thread
 player_label = "Player 1" if is_player1 else "Player 2"
 await interaction.response.send_message(
 f"■ **{player_label}** ({user.mention}) picked **{matched_item}** ({required_role.capitalize()})!",
 ephemeral=False
 )

 # Check round progression
 total_picks = len(match.player1_picks) + len(match.player2_picks)

 if total_picks == 6: # All picks done (3 rounds x 2 players)
 match.current_phase = "results"
 await match.thread.send(
 "■ **PICK PHASE COMPLETE!**\n"
 f"**Current Score:** {match.player1_score}-{match.player2_score}\n"
 f"Play **Round {match.rounds_completed + 1}** and use `/iwon` or `/ilose` to report the result!"
 )
 await self.update_status_message(match)
 elif total_picks % 2 == 0: # Round complete
 match.current_round += 1
 match.current_turn = match.player2 if match.current_round == 2 else match.player1 # FIXED: Round 2 starts with P2
 await match.thread.send(f"■ **Round {match.current_round} starting...**")
 await self.update_status_message(match)
 else:
 # Switch turn
 match.current_turn = match.player2 if is_player1 else match.player1
 await self.update_status_message(match)

 async def handle_result(self, interaction: discord.Interaction, result: str):
 """Handle win/loss claims - UPDATED FOR ROUND-BY-ROUND SCORING"""
 thread_id = interaction.channel_id

 if thread_id not in self.active_matches:
 await interaction.response.send_message("■ No active match in this thread!", ephemeral=True)
 return

 match = self.active_matches[thread_id]
 user = interaction.user

 # Check if pick phase is complete
 if match.current_phase != "results":
 await interaction.response.send_message("■ Complete the pick phase first!", ephemeral=True)
 return

 # Determine which player
 is_player1 = user.id == match.player1.id
 is_player2 = user.id == match.player2.id

 if not (is_player1 or is_player2):
 await interaction.response.send_message("■ You're not in this match!", ephemeral=True)
 return

 # Record claim
 if is_player1:
 if match.player1_claimed:
 await interaction.response.send_message("■ You already submitted your result for this round!", ephemeral=True)
 return
 match.player1_claimed = result
 else:
 if match.player2_claimed:
 await interaction.response.send_message("■ You already submitted your result for this round!", ephemeral=True)
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
 "■ **Results don't match!** Please verify who won this round.",
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
 title="■ Match Complete!",
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

 # Clean up
 match.match_complete = True
 del self.active_matches[thread_id]
 # Archive thread after 5 minutes
 await match.thread.edit(auto_archive_duration=5)
 else:
 # More rounds to play
 embed = discord.Embed(
 title=f"■ Round {match.rounds_completed} Complete!",
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
 f"■ You claimed a **{result}** for Round {match.rounds_completed + 1}.\n"
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
 await interaction.response.send_message("■ No active match in this thread!", ephemeral=True)
 return

 match = self.active_matches[thread_id]

 # Check if user is in this match
 if user.id != match.player1.id and user.id != match.player2.id:
 await interaction.response.send_message("■ You're not in this match!", ephemeral=True)
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
 title="■ Match Cancelled",
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
================================================================================
# FILE: team_matchmaking_part1.py (170 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 1
Party System
Create parties, invite players, manage teams
"""
import discord
from typing import List, Dict, Optional, Tuple
from datetime import datetime
class Party:
 """Represents a party/team"""
 def __init__(self, host: discord.Member):
 self.host = host
 self.members: List[discord.Member] = [host]
 self.pending_invites: Dict[int, datetime] = {} # user_id -> invite_time
 self.created_at = datetime.now()
 self.max_size = 5

 def add_member(self, member: discord.Member) -> bool:
 """Add member to party"""
 if len(self.members) >= self.max_size:
 return False
 if member.id in [m.id for m in self.members]:
 return False
 self.members.append(member)
 return True

 def remove_member(self, member: discord.Member) -> bool:
 """Remove member from party"""
 if member.id == self.host.id:
 return False # Can't remove host
 for m in self.members:
 if m.id == member.id:
 self.members.remove(m)
 return True
 return False

 def is_host(self, user: discord.Member) -> bool:
 """Check if user is host"""
 return user.id == self.host.id

 def is_member(self, user: discord.Member) -> bool:
 """Check if user is in party"""
 return user.id in [m.id for m in self.members]

 def get_size(self) -> int:
 """Get party size"""
 return len(self.members)
class PartySystem:
 """Manages all parties"""
 def __init__(self):
 self.parties: Dict[int, Party] = {} # host_id -> Party
 self.user_party_map: Dict[int, int] = {} # user_id -> host_id

 def create_party(self, host: discord.Member) -> Tuple[bool, str]:
 """Create a new party"""
 if host.id in self.user_party_map:
 return False, "You're already in a party!"

 party = Party(host)
 self.parties[host.id] = party
 self.user_party_map[host.id] = host.id
 return True, "■ Party created! Use `/partyinvite @user` to invite members."
 def get_user_party(self, user: discord.Member) -> Optional[Party]:
 """Get the party a user is in"""
 if user.id not in self.user_party_map:
 return None
 host_id = self.user_party_map[user.id]
 return self.parties.get(host_id)

 def invite_to_party(self, host: discord.Member, target: discord.Member) -> Tuple[bool, str]:
 """Invite user to party"""
 party = self.parties.get(host.id)
 if not party:
 return False, "You don't have a party! Use `/party` to create one."

 if not party.is_host(host):
 return False, "Only the host can invite members!"

 if party.get_size() >= party.max_size:
 return False, f"Party is full! (Max {party.max_size} members)"

 if target.id in self.user_party_map:
 return False, f"{target.display_name} is already in a party!"

 if target.id in party.pending_invites:
 return False, f"{target.display_name} already has a pending invite!"

 party.pending_invites[target.id] = datetime.now()
 return True, f"■ Invited {target.mention} to the party!"

 def accept_invite(self, user: discord.Member, host: discord.Member) -> Tuple[bool, str]:
 """Accept party invite"""
 if user.id in self.user_party_map:
 return False, "You're already in a party!"

 party = self.parties.get(host.id)
 if not party:
 return False, "That party no longer exists!"

 if user.id not in party.pending_invites:
 return False, f"You don't have a pending invite from {host.display_name}!"

 if party.get_size() >= party.max_size:
 del party.pending_invites[user.id]
 return False, "Party is full!"

 # Accept invite
 party.add_member(user)
 del party.pending_invites[user.id]
 self.user_party_map[user.id] = host.id

 return True, f"■ Joined {host.display_name}'s party! ({party.get_size()}/{party.max_size})"

 def decline_invite(self, user: discord.Member, host: discord.Member) -> Tuple[bool, str]:
 """Decline party invite"""
 party = self.parties.get(host.id)
 if not party:
 return False, "That party no longer exists!"

 if user.id not in party.pending_invites:
 return False, f"You don't have a pending invite from {host.display_name}!"

 del party.pending_invites[user.id]
 return True, f"■ Declined invite from {host.display_name}."

 def leave_party(self, user: discord.Member) -> Tuple[bool, str]:
 """Leave party"""
 party = self.get_user_party(user)
 if not party:
 return False, "You're not in a party!"

 if party.is_host(user):
 # Disband party
 for member in party.members:
 if member.id in self.user_party_map:
 del self.user_party_map[member.id]
 del self.parties[user.id]
 return True, "■ Party disbanded."

 # Remove member
 party.remove_member(user)
 del self.user_party_map[user.id]
 return True, f"■ Left the party."

 def kick_member(self, host: discord.Member, target: discord.Member) -> Tuple[bool, str]:
 """Kick member from party"""
 party = self.parties.get(host.id)
 if not party:
 return False, "You don't have a party!"

 if not party.is_host(host):
 return False, "Only the host can kick members!"

 if target.id == host.id:
 return False, "You can't kick yourself! Use `/partydisband` instead."

 if not party.is_member(target):
 return False, f"{target.display_name} is not in your party!"

 party.remove_member(target)
 if target.id in self.user_party_map:
 del self.user_party_map[target.id]

 return True, f"■ Kicked {target.display_name} from the party."
================================================================================
# FILE: team_matchmaking_part2.py (209 lines)
================================================================================
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
 "2v2": 1, # 1 ban per team
 "3v3": 0, # No bans
 "4v4": 0 # No bans
}
class TeamMatch:
 """Represents a team match (2v2, 3v3, or 4v4)"""
 def __init__(self, team_a: List[discord.Member], team_b: List[discord.Member],
 mode: str, channel: discord.TextChannel):
 self.team_a = team_a
 self.team_b = team_b
 self.mode = mode # "2v2", "3v3", or "4v4"
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
 "2v2": 4, # Each player gets 2 rounds
 "3v3": 6, # Each player gets 2 rounds
 "4v4": 8 # Each player gets 2 rounds
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

 else: # 4v4
 # 8 rounds: each player gets killer once
 patterns = [
 {"team_a": ["killer", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "surv {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["killer", "survivor", "survivor", "surv {"team_a": ["survivor", "killer", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "surv {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "killer", "survivor", "surv {"team_a": ["survivor", "survivor", "killer", "survivor"], "team_b": ["survivor", "survivor", "survivor", "surv {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "killer", "surv {"team_a": ["survivor", "survivor", "survivor", "killer"], "team_b": ["survivor", "survivor", "survivor", "surv {"team_a": ["survivor", "survivor", "survivor", "survivor"], "team_b": ["survivor", "survivor", "survivor", "ki ]
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
================================================================================
# FILE: team_matchmaking_part3.py (223 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 3
Queue System
Manages matchmaking queues for 2v2, 3v3, 4v4
"""
import discord
from typing import Dict, Optional, List
from team_matchmaking_part2 import TeamMatch
import random
class TeamQueue:
 """Queue for team matchmaking"""
 def __init__(self, mode: str):
 self.mode = mode
 self.waiting_teams: Dict[int, List[discord.Member]] = {} # host_id -> team
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
 self.active_matches: Dict[int, TeamMatch] = {} # thread_id -> TeamMatch
 self.ALLOWED_CHANNEL_ID = 1465526001110093834
 self.multi_mode_stats = None # Will be linked later

 async def queue_for_match(self, interaction: discord.Interaction, mode: str):
 """Queue a party for team matchmaking"""
 # Check channel
 if interaction.channel_id != self.ALLOWED_CHANNEL_ID:
 await interaction.response.send_message(
 f"■ Team matchmaking can only be used in <#{self.ALLOWED_CHANNEL_ID}>!",
 ephemeral=True
 )
 return

 user = interaction.user
 # Get user's party
 party = self.party_system.get_user_party(user)
 if not party:
 await interaction.response.send_message(
 "■ You need a party first! Use `/party` to create one.",
 ephemeral=True
 )
 return

 # Must be host
 if not party.is_host(user):
 await interaction.response.send_message(
 "■ Only the party host can queue for matches!",
 ephemeral=True
 )
 return

 # Check party size
 required_size = {"2v2": 2, "3v3": 3, "4v4": 4}[mode]
 party_size = party.get_size()

 if party_size > required_size:
 await interaction.response.send_message(
 f"■ Party too large for {mode}! Need exactly {required_size}, have {party_size}.\n"
 f"Kick extra members with `/partykick`.",
 ephemeral=True
 )
 return

 # Auto-fill with random players if needed
 team = list(party.members)
 if party_size < required_size:
 # For now, just require exact size
 await interaction.response.send_message(
 f"■ Party too small for {mode}! Need {required_size}, have {party_size}.\n"
 f"Invite more members with `/partyinvite`.",
 ephemeral=True
 )
 return

 # Add to queue
 queue = self.queues[mode]
 if not queue.add_team(user, team):
 await interaction.response.send_message(
 f"■ You're already in the {mode} queue!",
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
 title=f"■ {mode.upper()} Matchmaking",
 description=f"**{user.display_name}'s team** is searching for opponents!",
 color=discord.Color.blue()
 )

 team_text = "\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(team)])
 embed.add_field(name="Your Team", value=team_text, inline=False)
 embed.add_field(name="Status", value="■ Waiting for another team...", inline=False)

 await interaction.response.send_message(embed=embed)

 async def cancel_queue(self, interaction: discord.Interaction):
 """Cancel queue"""
 user = interaction.user

 # Check all queues
 for mode, queue in self.queues.items():
 if queue.remove_team(user.id):
 await interaction.response.send_message(
 f"■ Removed from {mode} queue.",
 ephemeral=True
 )
 return

 await interaction.response.send_message(
 "■ You're not in any queue!",
 ephemeral=True
 )

 async def create_team_match(self, interaction: discord.Interaction,
 team_a: List[discord.Member], team_b: List[discord.Member],
 mode: str):
 """Create a team match"""
 match = TeamMatch(team_a, team_b, mode, interaction.channel)

 # Create embed
 embed = discord.Embed(
 title=f"■■ {mode.upper()} Match Starting!",
 color=discord.Color.green()
 )

 team_a_text = "\n".join([f"{i+1}. {m.mention} {'■' if i == 0 else ''}"
 for i, m in enumerate(team_a)])
 team_b_text = "\n".join([f"{i+1}. {m.mention} {'■' if i == 0 else ''}"
 for i, m in enumerate(team_b)])

 embed.add_field(name="■ Team A", value=team_a_text, inline=True)
 embed.add_field(name="■ Team B", value=team_b_text, inline=True)

 await interaction.response.send_message(embed=embed)
 message = await interaction.original_response()

 # Create thread
 thread = await message.create_thread(
 name=f"■■ {mode.upper()}: {team_a[0].display_name} vs {team_b[0].display_name}",
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
 f"■ **BAN PHASE**\n"
 f"Hosts use `/teamban <character>` to ban!\n"
 f"Each team can ban {match.get_ban_limit()} character(s)."
 )
 else:
 await thread.send(
 f"■ **PICK PHASE - Round 1**\n"
 f"Use `/teampick <character>` to pick your character!\n"
 f"Check your role assignment below."
 )

 await self.update_match_status(match)

 async def update_match_status(self, match: TeamMatch):
 """Update match status message"""
 # Implementation in Part 4
 pass
================================================================================
# FILE: team_matchmaking_part4.py (86 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 4
Match Status and Display
Creates status embeds and updates
"""
import discord
from team_matchmaking_part2 import SURVIVORS, KILLERS, TEAM_BAN_LIMITS
async def update_match_status(team_mm_system, match):
 """Update or create match status message"""
 embed = create_match_status_embed(match)

 if match.status_message:
 try:
 await match.status_message.edit(embed=embed)
 except:
 match.status_message = await match.thread.send(embed=embed)
 else:
 match.status_message = await match.thread.send(embed=embed)
def create_match_status_embed(match) -> discord.Embed:
 """Create comprehensive status embed"""
 embed = discord.Embed(
 title=f"■ {match.mode.upper()} Match Status",
 color=discord.Color.gold()
 )

 # Phase indicator
 phase_text = {
 "ban": "■ BAN PHASE",
 "pick": f"■ PICK PHASE - Round {match.current_round}",
 "results": f"■ RESULTS - Round {match.current_round}"
 }.get(match.current_phase, "Unknown")

 embed.description = f"**Phase:** {phase_text}\n**Score:** {match.team_a_score}-{match.team_b_score}"

 # Bans
 if match.get_ban_limit() > 0:
 ban_a = ", ".join(match.team_a_bans) if match.team_a_bans else "None"
 ban_b = ", ".join(match.team_b_bans) if match.team_b_bans else "None"

 embed.add_field(
 name="■ Bans",
 value=f"**Team A:** {ban_a}\n**Team B:** {ban_b}",
 inline=False
 )

 # Round assignments
 if match.current_phase == "pick":
 pattern = match.get_round_pattern(match.current_round)

 team_a_roles = []
 for i, role in enumerate(pattern["team_a"]):
 player = match.team_a[i]
 pick = match.team_a_picks.get(i, "■")
 emoji = "■■" if role == "killer" else "■"
 team_a_roles.append(f"{emoji} {player.display_name}: {pick}")

 team_b_roles = []
 for i, role in enumerate(pattern["team_b"]):
 player = match.team_b[i]
 pick = match.team_b_picks.get(i, "■")
 emoji = "■■" if role == "killer" else "■"
 team_b_roles.append(f"{emoji} {player.display_name}: {pick}")

 embed.add_field(
 name="■ Team A Picks",
 value="\n".join(team_a_roles),
 inline=True
 )
 embed.add_field(
 name="■ Team B Picks",
 value="\n".join(team_b_roles),
 inline=True
 )

 return embed
# Add this method to TeamMatchmakingSystem
def setup_update_method(team_mm_system):
 """Link update method to system"""
 team_mm_system.update_match_status = lambda match: update_match_status(team_mm_system, match)
================================================================================
# FILE: team_matchmaking_part5.py (31 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 5
Team Commands Setup
Slash commands for team matchmaking
"""
import discord
from discord import app_commands
from typing import Optional
def setup_team_commands(tree: app_commands.CommandTree, team_mm_system):
 """Setup team matchmaking commands"""

 @tree.command(name="2v2", description="Queue for 2v2 matchmaking")
 async def queue_2v2(interaction: discord.Interaction):
 await team_mm_system.queue_for_match(interaction, "2v2")

 @tree.command(name="3v3", description="Queue for 3v3 matchmaking")
 async def queue_3v3(interaction: discord.Interaction):
 await team_mm_system.queue_for_match(interaction, "3v3")

 @tree.command(name="4v4", description="Queue for 4v4 matchmaking")
 async def queue_4v4(interaction: discord.Interaction):
 await team_mm_system.queue_for_match(interaction, "4v4")

 @tree.command(name="cancelqueue", description="Cancel matchmaking queue")
 async def cancel_queue(interaction: discord.Interaction):
 await team_mm_system.cancel_queue(interaction)

 return team_mm_system
================================================================================
# FILE: team_matchmaking_part6.py (404 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 6
Team Match Game Logic
Handles ban/pick phases, round progression, and result reporting for team matches
"""
import discord
from discord import app_commands
from typing import Optional
from team_matchmaking_part2 import SURVIVORS, KILLERS, TEAM_POINTS
class TeamGameLogic:
 """Handles game logic for team matches"""

 @staticmethod
 async def handle_team_ban(interaction: discord.Interaction, team_mm_system, character: str):
 """Handle team ban command"""
 thread_id = interaction.channel_id

 if thread_id not in team_mm_system.active_matches:
 await interaction.response.send_message("■ No active team match!", ephemeral=True)
 return

 match = team_mm_system.active_matches[thread_id]
 user = interaction.user

 # Check if ban phase
 if match.current_phase != "ban":
 await interaction.response.send_message("■ Not in ban phase!", ephemeral=True)
 return

 # Check if user is a team host
 team = match.is_team_host(user)
 if not team:
 await interaction.response.send_message("■ Only team hosts can ban!", ephemeral=True)
 return

 # Check if team can still ban
 if not match.can_ban(team):
 await interaction.response.send_message(
 f"■ Your team has already banned {match.get_ban_limit()} character(s)!",
 ephemeral=True
 )
 return

 # Normalize and validate character
 all_chars = SURVIVORS + KILLERS
 normalized = character.lower().replace(" ", "")

 matched_char = None
 for char in all_chars:
 if char.lower().replace(" ", "") == normalized:
 matched_char = char
 break

 if not matched_char:
 await interaction.response.send_message(f"■ Invalid character: {character}", ephemeral=True)
 return

 # Check if already banned
 if matched_char in match.team_a_bans or matched_char in match.team_b_bans:
 await interaction.response.send_message(f"■ {matched_char} is already banned!", ephemeral=True)
 return

 # Add ban
 match.add_ban(team, matched_char)

 # Announce
 team_name = "Team A ■" if team == "A" else "Team B ■"
 await interaction.response.send_message(
 f"■ **{team_name}** banned **{matched_char}**!",
 ephemeral=False
 )

 # Check if ban phase is complete
 ban_limit = match.get_ban_limit()
 if len(match.team_a_bans) >= ban_limit and len(match.team_b_bans) >= ban_limit:
 match.current_phase = "pick"
 await match.thread.send("■ **BAN PHASE COMPLETE!** Starting **PICK PHASE - Round 1**...")

 await team_mm_system.update_match_status(match)

 @staticmethod
 async def handle_team_pick(interaction: discord.Interaction, team_mm_system, character: str):
 """Handle team pick command"""
 thread_id = interaction.channel_id

 if thread_id not in team_mm_system.active_matches:
 await interaction.response.send_message("■ No active team match!", ephemeral=True)
 return

 match = team_mm_system.active_matches[thread_id]
 user = interaction.user

 # Check if pick phase
 if match.current_phase != "pick":
 await interaction.response.send_message("■ Not in pick phase!", ephemeral=True)
 return

 # Get user's team
 team = match.get_user_team(user)
 if not team:
 await interaction.response.send_message("■ You're not in this match!", ephemeral=True)
 return

 # Get user's index in team
 team_members = match.get_team_members(team)
 user_index = None
 for i, member in enumerate(team_members):
 if member.id == user.id:
 user_index = i
 break

 if user_index is None:
 await interaction.response.send_message("■ Could not find your position!", ephemeral=True)
 return

 # Get round pattern
 pattern = match.get_round_pattern(match.current_round)
 team_pattern = pattern[f"team_{team.lower()}"]

 if user_index >= len(team_pattern):
 await interaction.response.send_message("■ You don't have a role this round!", ephemeral=True)
 return

 required_role = team_pattern[user_index]

 # Check if already picked
 picks = match.team_a_picks if team == "A" else match.team_b_picks
 if user_index in picks:
 await interaction.response.send_message(
 f"■ You've already picked {picks[user_index]}!",
 ephemeral=True
 )
 return

 # Validate character
 if required_role == "killer":
 valid_pool = KILLERS
 else:
 valid_pool = SURVIVORS

 # Normalize
 normalized = character.lower().replace(" ", "")
 matched_char = None
 for char in valid_pool:
 if char.lower().replace(" ", "") == normalized:
 matched_char = char
 break

 if not matched_char:
 await interaction.response.send_message(
 f"■ You must pick a **{required_role}**! {character} is not valid.",
 ephemeral=True
 )
 return

 # Check if banned
 if matched_char in match.team_a_bans or matched_char in match.team_b_bans:
 await interaction.response.send_message(f"■ {matched_char} is banned!", ephemeral=True)
 return

 # Check if already picked by team (survivors only)
 if required_role == "survivor":
 if matched_char in picks.values():
 await interaction.response.send_message(
 f"■ {matched_char} is already picked by your team!",
 ephemeral=True
 )
 return

 # Add pick
 match.add_pick(team, user_index, matched_char)

 # Announce
 team_name = "Team A ■" if team == "A" else "Team B ■"
 await interaction.response.send_message(
 f"■ **{team_name}** {user.mention} picked **{matched_char}** ({required_role.capitalize()})!",
 ephemeral=False
 )

 # Check if round is complete
 if match.is_pick_phase_complete():
 match.current_phase = "results"
 await match.thread.send(
 f"■ **ROUND {match.current_round} PICKS COMPLETE!**\n"
 f"**Current Score:** {match.team_a_score}-{match.team_b_score}\n"
 f"Play the round and hosts use `/teamwon` or `/teamloss` to report!"
 )

 await team_mm_system.update_match_status(match)

 @staticmethod
 async def handle_team_result(interaction: discord.Interaction, team_mm_system, result: str):
 """Handle team match result reporting"""
 thread_id = interaction.channel_id

 if thread_id not in team_mm_system.active_matches:
 await interaction.response.send_message("■ No active team match!", ephemeral=True)
 return

 match = team_mm_system.active_matches[thread_id]
 user = interaction.user

 # Check if results phase
 if match.current_phase != "results":
 await interaction.response.send_message("■ Complete the pick phase first!", ephemeral=True)
 return

 # Check if user is a team host
 team = match.is_team_host(user)
 if not team:
 await interaction.response.send_message("■ Only team hosts can report results!", ephemeral=True)
 return

 # Record claim
 if team == "A":
 if match.team_a_claimed:
 await interaction.response.send_message("■ Your team already reported!", ephemeral=True)
 return
 match.team_a_claimed = result
 else:
 if match.team_b_claimed:
 await interaction.response.send_message("■ Your team already reported!", ephemeral=True)
 return
 match.team_b_claimed = result

 # Check if both reported
 if match.team_a_claimed and match.team_b_claimed:
 # Validate
 valid = (
 (match.team_a_claimed == "win" and match.team_b_claimed == "loss") or
 (match.team_a_claimed == "loss" and match.team_b_claimed == "win")
 )

 if not valid:
 await interaction.response.send_message(
 "■ **Results don't match!** Please verify who won.",
 ephemeral=False
 )
 match.team_a_claimed = None
 match.team_b_claimed = None
 return

 # Update scores
 if match.team_a_claimed == "win":
 match.team_a_score += 1
 else:
 match.team_b_score += 1

 match.rounds_completed += 1

 # Check if match over
 match_over = match.rounds_completed >= match.total_rounds

 # Check for tiebreaker
 if match_over and match.check_for_tiebreaker():
 match.in_tiebreaker = True
 match.current_phase = "pick"
 match.current_round = match.total_rounds # Repeat last round
 match.reset_picks_for_next_round()

 await interaction.response.send_message(
 f"■■ **TIEBREAKER!** Score is tied {match.team_a_score}-{match.team_b_score}\n"
 f"Playing Round {match.current_round} again!",
 ephemeral=False
 )
 await team_mm_system.update_match_status(match)
 return

 if match_over:
 # Match complete!
 await TeamGameLogic.finalize_team_match(interaction, team_mm_system, match)
 else:
 # Next round
 match.current_phase = "pick"
 match.current_round += 1
 match.reset_picks_for_next_round()
 match.team_a_claimed = None
 match.team_b_claimed = None

 await interaction.response.send_message(
 f"■ **Round {match.rounds_completed} Complete!**\n"
 f"**Score:** {match.team_a_score}-{match.team_b_score}\n"
 f"Starting Round {match.current_round}...",
 ephemeral=False
 )
 await team_mm_system.update_match_status(match)
 else:
 # Waiting
 other_team = "B" if team == "A" else "A"
 other_host = match.get_team_host(other_team)
 await interaction.response.send_message(
 f"■ Team {team} reported a **{result}**.\n"
 f"Waiting for {other_host.mention} (Team {other_team}) to report...",
 ephemeral=False
 )

 @staticmethod
 async def finalize_team_match(interaction, team_mm_system, match):
 """Finalize and award points for team match"""
 # Determine winner
 if match.team_a_score > match.team_b_score:
 winning_team = match.team_a
 losing_team = match.team_b
 winner_name = "Team A ■"
 loser_name = "Team B ■"
 else:
 winning_team = match.team_b
 losing_team = match.team_a
 winner_name = "Team B ■"
 loser_name = "Team A ■"

 # Get points
 win_points = TEAM_POINTS[match.mode]["win"]
 loss_points = TEAM_POINTS[match.mode]["loss"]

 # Award points to all team members
 for member in winning_team:
 stats = team_mm_system.multi_mode_stats.get_or_create_stats(member, match.mode)
 stats.points += win_points
 stats.wins += 1

 for member in losing_team:
 stats = team_mm_system.multi_mode_stats.get_or_create_stats(member, match.mode)
 stats.points = max(0, stats.points + loss_points) # Prevent negative
 stats.losses += 1

 team_mm_system.multi_mode_stats.save_stats()

 embed = discord.Embed(
 title=f"■ {match.mode.upper()} Match Complete!",
 description=f"**{winner_name}** wins!",
 color=discord.Color.gold()
 )
 embed.add_field(
 name="Final Score",
 value=f"```\n{match.team_a_score}-{match.team_b_score}\n```",
 inline=False
 )
 embed.add_field(
 name="Points",
 value=f"**{winner_name}:** +{win_points} points each\n"
 f"**{loser_name}:** {loss_points} points each",
 inline=False
 )

 await interaction.response.send_message(embed=embed)

 # Clean up
 del team_mm_system.active_matches[match.thread.id]

 # Auto-close thread
 await match.thread.edit(archived=True)

 @staticmethod
 def get_pick_autocomplete(match, user_id, current: str):
 """Get autocomplete choices for team pick"""
 team = match.get_user_team_by_id(user_id)
 if not team:
 return []

 team_members = match.get_team_members(team)
 user_index = None
 for i, member in enumerate(team_members):
 if member.id == user_id:
 user_index = i
 break

 if user_index is None:
 return []

 pattern = match.get_round_pattern(match.current_round)
 team_pattern = pattern[f"team_{team.lower()}"]

 if user_index >= len(team_pattern):
 return []

 role = team_pattern[user_index]

 # Get available characters
 if role == "killer":
 available = match.get_available_killers()
 else:
 available = match.get_available_survivors(team)

 # Filter by current input
 if current:
 available = [c for c in available if current.lower() in c.lower()]

 return [app_commands.Choice(name=c, value=c) for c in available[:25]]

 @staticmethod
 def get_ban_autocomplete(match, current: str):
 """Get autocomplete choices for team ban"""
 all_chars = SURVIVORS + KILLERS
 banned = match.team_a_bans + match.team_b_bans
 available = [c for c in all_chars if c not in banned]

 if current:
 available = [c for c in available if current.lower() in c.lower()]

 return [app_commands.Choice(name=c, value=c) for c in available[:25]]
================================================================================
# FILE: team_matchmaking_part7.py (206 lines)
================================================================================
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
 self.mode = mode # "1v1", "2v2", "3v3", "4v4"
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
 print(f"■ Auto-fixed {fixed_count} player(s) with negative points")
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
 mode = "1v1" # Default

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
 title=f"■ {stats.mode.upper()} Stats for {user.display_name}",
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
 title=f"■ All Stats for {user.display_name}",
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
 title=f"■ {mode.upper()} Leaderboard - Top 10",
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
================================================================================
# FILE: team_matchmaking_part8.py (528 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 8
Complete Command Setup
Integrates all systems: 1v1, Party, Team Matchmaking, Multi-Mode Stats
"""
import discord
from discord import app_commands
from typing import Optional
from team_matchmaking_part1 import PartySystem
from team_matchmaking_part3 import TeamMatchmakingSystem
from team_matchmaking_part6 import TeamGameLogic
from team_matchmaking_part7 import (
 MultiModeStatsSystem,
 create_stats_embed,
 create_multi_mode_stats_embed,
 create_leaderboard_embed
)
from team_matchmaking_part11 import Tournament5v5System
from team_matchmaking_part13 import setup_5v5_tournament_commands
from team_matchmaking_part14 import (
 ProfileSystem,
 create_profile_embed,
 handle_profile_banner_set,
 handle_profile_bio_set,
 handle_profile_main_set,
 handle_profile_stats_set
)
def setup_all_commands(bot_client, tree: app_commands.CommandTree, matchmaking_1v1=None):
 """
 Setup all commands for the bot
 - Party commands
 - Team matchmaking commands (2v2, 3v3, 4v4)
 - Multi-mode stats commands
 - Team match game commands (ban, pick, result)
 """

 # Initialize systems
 party_system = PartySystem()
 multi_mode_stats = MultiModeStatsSystem()
 profile_system = ProfileSystem()
 team_mm_system = TeamMatchmakingSystem(party_system)
 team_mm_system.multi_mode_stats = multi_mode_stats # Link stats system
 tournament_5v5_system = Tournament5v5System(party_system)
 tournament_5v5_system.multi_mode_stats = multi_mode_stats # Link stats system

 # ==================== PARTY COMMANDS ====================

 @tree.command(name="party", description="Create a new party")
 async def create_party(interaction: discord.Interaction):
 success, message = party_system.create_party(interaction.user)

 if success:
 party = party_system.get_user_party(interaction.user)
 embed = discord.Embed(
 title="■ Party Created!",
 description=f"{interaction.user.mention} created a party!",
 color=discord.Color.green()
 )
 embed.add_field(
 name="Members",
 value=f"1. {interaction.user.mention} (Host)",
 inline=False
 )
 embed.add_field(
 name="Available Commands",
 value=(
 "`/partyinvite @user` - Invite someone\n"
 "`/partymembers` - View members\n"
 "`/2v2` or `/3v3` or `/4v4` - Start matchmaking"
 ),
 inline=False
 )
 await interaction.response.send_message(embed=embed)
 else:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partyleave", description="Leave your current party")
 async def leave_party(interaction: discord.Interaction):
 success, message = party_system.leave_party(interaction.user)
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partydisband", description="Disband your party (host only)")
 async def disband_party(interaction: discord.Interaction):
 success, message = party_system.disband_party(interaction.user)
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partyinvite", description="Invite someone to your party")
 @app_commands.describe(user="User to invite")
 async def invite_party(interaction: discord.Interaction, user: discord.Member):
 success, message = party_system.invite_to_party(interaction.user, user)

 if success:
 await interaction.response.send_message(
 f"■ {user.mention} You've been invited to {interaction.user.mention}'s party!\n"
 f"Use `/partyaccept @{interaction.user.name}` to join!"
 )
 else:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partyaccept", description="Accept a party invite")
 @app_commands.describe(host="Party host who invited you")
 async def accept_party(interaction: discord.Interaction, host: discord.Member):
 success, message = party_system.accept_invite(interaction.user, host)

 if success:
 party = party_system.get_user_party(interaction.user)
 members_text = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(party.members)])

 embed = discord.Embed(
 title="■ Joined Party!",
 description=f"{interaction.user.mention} joined {host.mention}'s party!",
 color=discord.Color.green()
 )
 embed.add_field(
 name=f"Members ({party.get_size()}/{party.max_size})",
 value=members_text,
 inline=False
 )
 await interaction.response.send_message(embed=embed)
 else:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partydecline", description="Decline a party invite")
 @app_commands.describe(host="Party host who invited you")
 async def decline_party(interaction: discord.Interaction, host: discord.Member):
 success, message = party_system.decline_invite(interaction.user, host)
 await interaction.response.send_message(message, ephemeral=True)
 @tree.command(name="partykick", description="Kick someone from your party (host only)")
 @app_commands.describe(user="User to kick")
 async def kick_party(interaction: discord.Interaction, user: discord.Member):
 success, message = party_system.kick_member(interaction.user, user)
 if success:
 await interaction.response.send_message(
 f"■ {user.mention} has been kicked from the party."
 )
 else:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="partymembers", description="View your party members")
 async def party_members(interaction: discord.Interaction):
 party = party_system.get_user_party(interaction.user)

 if not party:
 await interaction.response.send_message("■ You're not in a party!", ephemeral=True)
 return

 embed = discord.Embed(
 title=f"■ Party Members ({party.get_size()}/{party.max_size})",
 description=f"**Host:** {party.host.mention}",
 color=discord.Color.blue()
 )

 members_text = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(party.members)])
 embed.add_field(name="Members", value=members_text, inline=False)

 if party.pending_invites:
 invites = [f"<@{uid}>" for uid in party.pending_invites.keys()]
 embed.add_field(name="Pending Invites", value="\n".join(invites), inline=False)

 await interaction.response.send_message(embed=embed)

 # ==================== TEAM MATCHMAKING COMMANDS ====================

 @tree.command(name="2v2", description="Queue for 2v2 match with your party")
 async def queue_2v2(interaction: discord.Interaction):
 success, message = await team_mm_system.start_queue(interaction, "2v2")

 if success and "Searching" in message:
 embed = discord.Embed(
 title="■ 2v2 Matchmaking",
 description=message,
 color=discord.Color.blue()
 )
 embed.add_field(
 name="Searching...",
 value="Waiting for another team to join the queue.",
 inline=False
 )
 await interaction.response.send_message(embed=embed)
 elif not success:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="3v3", description="Queue for 3v3 match with your party")
 async def queue_3v3(interaction: discord.Interaction):
 success, message = await team_mm_system.start_queue(interaction, "3v3")

 if success and "Searching" in message:
 embed = discord.Embed(
 title="■ 3v3 Matchmaking",
 description=message,
 color=discord.Color.blue()
 )
 await interaction.response.send_message(embed=embed)
 elif not success:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="4v4", description="Queue for 4v4 match with your party")
 async def queue_4v4(interaction: discord.Interaction):
 success, message = await team_mm_system.start_queue(interaction, "4v4")

 if success and "Searching" in message:
 embed = discord.Embed(
 title="■ 4v4 Matchmaking",
 description=message,
 color=discord.Color.blue()
 )
 await interaction.response.send_message(embed=embed)
 elif not success:
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="cancelqueue", description="Cancel your matchmaking queue")
 async def cancel_queue(interaction: discord.Interaction):
 success, message = await team_mm_system.cancel_queue(interaction)
 await interaction.response.send_message(message, ephemeral=True)

 @tree.command(name="teamcancel", description="Cancel team match (host only, no penalty)")
 async def team_cancel(interaction: discord.Interaction):
 thread_id = interaction.channel_id

 if thread_id not in team_mm_system.active_matches:
 await interaction.response.send_message("■ No active team match in this thread!", ephemeral=True)
 return

 match = team_mm_system.active_matches[thread_id]
 user = interaction.user

 team = match.is_team_host(user)
 if not team:
 await interaction.response.send_message("■ Only team hosts can cancel the match!", ephemeral=True)
 return

 embed = discord.Embed(
 title="■ Match Cancelled",
 description=f"Match cancelled by {user.mention} (Team {team} Host)",
 color=discord.Color.red()
 )
 embed.add_field(
 name="Result",
 value="No points affected. Match ended without completion.",
 inline=False
 )

 await interaction.response.send_message(embed=embed)

 del team_mm_system.active_matches[thread_id]
 await match.thread.edit(archived=True)

 # ==================== TEAM GAME COMMANDS ====================

 @tree.command(name="teamban", description="Ban a character (host only, 2v2 mode)")
 @app_commands.describe(character="Character to ban")
 async def team_ban(interaction: discord.Interaction, character: str):
 await TeamGameLogic.handle_team_ban(interaction, team_mm_system, character)

 @team_ban.autocomplete('character')
 async def team_ban_autocomplete(interaction: discord.Interaction, current: str):
 thread_id = interaction.channel_id
 if thread_id not in team_mm_system.active_matches:
 return []

 match = team_mm_system.active_matches[thread_id]
 return TeamGameLogic.get_ban_autocomplete(match, current)

 @tree.command(name="teampick", description="Pick your character for the current round")
 @app_commands.describe(character="Character to pick")
 async def team_pick(interaction: discord.Interaction, character: str):
 await TeamGameLogic.handle_team_pick(interaction, team_mm_system, character)

 @team_pick.autocomplete('character')
 async def team_pick_autocomplete(interaction: discord.Interaction, current: str):
 thread_id = interaction.channel_id
 if thread_id not in team_mm_system.active_matches:
 return []

 match = team_mm_system.active_matches[thread_id]
 return TeamGameLogic.get_pick_autocomplete(match, interaction.user.id, current)

 @tree.command(name="teamwon", description="Report your team won the round (host only)")
 async def team_won(interaction: discord.Interaction):
 await TeamGameLogic.handle_team_result(interaction, team_mm_system, "win")

 @tree.command(name="teamloss", description="Report your team lost the round (host only)")
 async def team_loss(interaction: discord.Interaction):
 await TeamGameLogic.handle_team_result(interaction, team_mm_system, "loss")

 # ==================== STATS COMMANDS ====================

 @tree.command(name="stats", description="View player profile and stats")
 @app_commands.describe(
 mode="Game mode (optional - leave blank to see profile)",
 user="User to check (optional)"
 )
 @app_commands.choices(mode=[
 app_commands.Choice(name="Profile (All Stats)", value="all"),
 app_commands.Choice(name="1v1", value="1v1"),
 app_commands.Choice(name="2v2", value="2v2"),
 app_commands.Choice(name="3v3", value="3v3"),
 app_commands.Choice(name="4v4", value="4v4"),
 app_commands.Choice(name="5v5 Tournament", value="5v5"),
 ])
 async def view_stats(interaction: discord.Interaction, mode: Optional[str] = "all",
 user: Optional[discord.Member] = None):
 target = user or interaction.user

 if mode == "all" or mode is None:
 # Show enhanced profile with banner
 profile = profile_system.get_or_create_profile(target)
 embed = create_profile_embed(target, profile, multi_mode_stats)
 else:
 # Show specific mode stats
 stats = multi_mode_stats.get_stats(target, mode)
 if not stats:
 stats = multi_mode_stats.get_or_create_stats(target, mode)
 embed = create_stats_embed(target, stats)

 await interaction.response.send_message(embed=embed)

 @tree.command(name="leaderboard", description="View leaderboard for a game mode")
 @app_commands.describe(mode="Game mode")
 @app_commands.choices(mode=[
 app_commands.Choice(name="1v1", value="1v1"),
 app_commands.Choice(name="2v2", value="2v2"),
 app_commands.Choice(name="3v3", value="3v3"),
 app_commands.Choice(name="4v4", value="4v4"),
 app_commands.Choice(name="5v5 Tournament", value="5v5"),
 ])
 async def leaderboard(interaction: discord.Interaction, mode: str):
 leaderboard_data = multi_mode_stats.get_leaderboard(mode, limit=10)
 embed = create_leaderboard_embed(mode, leaderboard_data)
 await interaction.response.send_message(embed=embed)

 # ==================== PROFILE CUSTOMIZATION COMMANDS ====================

 @tree.command(name="profilebanner", description="Set your profile banner image")
 @app_commands.describe(banner_url="Discord CDN image URL (right-click image → Copy Link)")
 async def profile_banner(interaction: discord.Interaction, banner_url: str):
 await handle_profile_banner_set(interaction, profile_system, banner_url)

 @tree.command(name="profilebio", description="Set your profile bio")
 @app_commands.describe(bio="Your bio text (max 200 characters)")
 async def profile_bio(interaction: discord.Interaction, bio: str):
 await handle_profile_bio_set(interaction, profile_system, bio)

 @tree.command(name="profilekiller", description="Set your main killer")
 @app_commands.describe(killer="Your main killer character")
 async def profile_killer(interaction: discord.Interaction, killer: str):
 await handle_profile_main_set(interaction, profile_system, "killer", killer)

 @profile_killer.autocomplete('killer')
 async def killer_autocomplete(interaction: discord.Interaction, current: str):
 from team_matchmaking_part10 import KILLERS
 filtered = [k for k in KILLERS if current.lower() in k.lower()] if current else KILLERS
 return [app_commands.Choice(name=k, value=k) for k in filtered[:25]]

 @tree.command(name="profilesurvivor", description="Set your main survivor")
 @app_commands.describe(survivor="Your main survivor character")
 async def profile_survivor(interaction: discord.Interaction, survivor: str):
 await handle_profile_main_set(interaction, profile_system, "survivor", survivor)

 @profile_survivor.autocomplete('survivor')
 async def survivor_autocomplete(interaction: discord.Interaction, current: str):
 from team_matchmaking_part10 import SURVIVORS
 filtered = [s for s in SURVIVORS if current.lower() in s.lower()] if current else SURVIVORS
 return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]

 @tree.command(name="profileplaytime", description="Set your playtime hours")
 @app_commands.describe(hours="Total playtime in hours")
 async def profile_playtime(interaction: discord.Interaction, hours: int):
 await handle_profile_stats_set(interaction, profile_system, "playtime", hours)
 @tree.command(name="profilekillerwin", description="Set your killer wins")
 @app_commands.describe(wins="Total killer wins")
 async def profile_killer_wins(interaction: discord.Interaction, wins: int):
 await handle_profile_stats_set(interaction, profile_system, "killerwin", wins)

 @tree.command(name="profilesurvivorwin", description="Set your survivor wins")
 @app_commands.describe(wins="Total survivor wins")
 async def profile_survivor_wins(interaction: discord.Interaction, wins: int):
 await handle_profile_stats_set(interaction, profile_system, "survivorwin", wins)

 # ==================== ADMIN COMMANDS ====================

 ADMIN_USER_ID = 822110342724190258

 @tree.command(name="setpoint", description="[ADMIN] Set a player's points for a mode")
 @app_commands.describe(user="Target user", mode="Game mode", points="New points value")
 @app_commands.choices(mode=[
 app_commands.Choice(name="1v1", value="1v1"),
 app_commands.Choice(name="2v2", value="2v2"),
 app_commands.Choice(name="3v3", value="3v3"),
 app_commands.Choice(name="4v4", value="4v4"),
 app_commands.Choice(name="5v5 Tournament", value="5v5"),
 ])
 async def set_point(interaction: discord.Interaction, user: discord.Member, mode: str, points: int):
 if interaction.user.id != ADMIN_USER_ID:
 await interaction.response.send_message("■ Admin only!", ephemeral=True)
 return

 stats = multi_mode_stats.get_or_create_stats(user, mode)
 old_points = stats.points
 stats.points = max(0, points)
 multi_mode_stats.save_stats()

 await interaction.response.send_message(
 f"■ Set {user.mention}'s {mode} points: {old_points} → {stats.points}",
 ephemeral=False
 )

 @tree.command(name="setwin", description="[ADMIN] Set a player's wins for a mode")
 @app_commands.describe(user="Target user", mode="Game mode", wins="New wins value")
 @app_commands.choices(mode=[
 app_commands.Choice(name="1v1", value="1v1"),
 app_commands.Choice(name="2v2", value="2v2"),
 app_commands.Choice(name="3v3", value="3v3"),
 app_commands.Choice(name="4v4", value="4v4"),
 app_commands.Choice(name="5v5 Tournament", value="5v5"),
 ])
 async def set_win(interaction: discord.Interaction, user: discord.Member, mode: str, wins: int):
 if interaction.user.id != ADMIN_USER_ID:
 await interaction.response.send_message("■ Admin only!", ephemeral=True)
 return

 stats = multi_mode_stats.get_or_create_stats(user, mode)
 stats.wins = max(0, wins)
 multi_mode_stats.save_stats()

 await interaction.response.send_message(
 f"■ Set {user.mention}'s {mode} wins to {stats.wins}",
 ephemeral=False
 )

 @tree.command(name="setloss", description="[ADMIN] Set a player's losses for a mode")
 @app_commands.describe(user="Target user", mode="Game mode", losses="New losses value")
 @app_commands.choices(mode=[
 app_commands.Choice(name="1v1", value="1v1"),
 app_commands.Choice(name="2v2", value="2v2"),
 app_commands.Choice(name="3v3", value="3v3"),
 app_commands.Choice(name="4v4", value="4v4"),
 app_commands.Choice(name="5v5 Tournament", value="5v5"),
 ])
 async def set_loss(interaction: discord.Interaction, user: discord.Member, mode: str, losses: int):
 if interaction.user.id != ADMIN_USER_ID:
 await interaction.response.send_message("■ Admin only!", ephemeral=True)
 return

 stats = multi_mode_stats.get_or_create_stats(user, mode)
 stats.losses = max(0, losses)
 multi_mode_stats.save_stats()

 await interaction.response.send_message(
 f"■ Set {user.mention}'s {mode} losses to {stats.losses}",
 ephemeral=False
 )

 @tree.command(name="close", description="[ADMIN] Force close any active match thread")
 async def admin_close(interaction: discord.Interaction):
 """Admin command to force close any match thread without both players"""
 if interaction.user.id != ADMIN_USER_ID:
 await interaction.response.send_message("■ Admin only!", ephemeral=True)
 return

 thread_id = interaction.channel_id
 closed = False

 # Check in team matches (2v2, 3v3, 4v4)
 if thread_id in team_mm_system.active_matches:
 match = team_mm_system.active_matches[thread_id]
 del team_mm_system.active_matches[thread_id]

 embed = discord.Embed(
 title="■ Match Closed by Admin",
 description=f"Match forcibly closed by {interaction.user.mention}",
 color=discord.Color.orange()
 )
 embed.add_field(
 name="Result",
 value="No points affected. Match terminated by admin.",
 inline=False
 )

 await interaction.response.send_message(embed=embed)
 await match.thread.edit(archived=True)
 closed = True

 # Check in 5v5 tournament matches
 elif thread_id in tournament_5v5_system.active_matches:
 match = tournament_5v5_system.active_matches[thread_id]
 del tournament_5v5_system.active_matches[thread_id]

 embed = discord.Embed(
 title="■ Tournament Closed by Admin",
 description=f"5v5 tournament forcibly closed by {interaction.user.mention}",
 color=discord.Color.orange()
 )
 embed.add_field(
 name="Result",
 value="No points affected. Tournament terminated by admin.",
 inline=False
 )

 await interaction.response.send_message(embed=embed)
 await match.thread.edit(archived=True)
 closed = True

 if not closed:
 await interaction.response.send_message(
 "■ No active match found in this thread!",
 ephemeral=True
 )

 # ==================== 5v5 TOURNAMENT COMMANDS ====================

 # Setup 5v5 tournament commands
 setup_5v5_tournament_commands(tree, tournament_5v5_system, multi_mode_stats)

 return {
 'party_system': party_system,
 'team_mm_system': team_mm_system,
 'tournament_5v5_system': tournament_5v5_system,
 'multi_mode_stats': multi_mode_stats,
 'profile_system': profile_system
 }
================================================================================
# FILE: team_matchmaking_part9.py (249 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 9
Helper Utilities
Additional helper methods for TeamMatch class
"""
import discord
from typing import Optional
class TeamMatchHelpers:
 """Helper methods for TeamMatch operations"""

 @staticmethod
 def add_helper_methods_to_match(match):
 """Add helper methods to a TeamMatch instance"""

 def get_user_team_by_id(user_id: int) -> Optional[str]:
 """Get which team a user is on by user ID"""
 if user_id in [m.id for m in match.team_a]:
 return "A"
 elif user_id in [m.id for m in match.team_b]:
 return "B"
 return None

 # Add method to match instance
 match.get_user_team_by_id = get_user_team_by_id
def create_team_roster_embed(match) -> discord.Embed:
 """Create a detailed team roster embed"""
 embed = discord.Embed(
 title=f"■ {match.mode.upper()} Team Rosters",
 color=discord.Color.blue()
 )

 # Team A
 team_a_text = []
 for i, member in enumerate(match.team_a):
 role = "■ Host" if member.id == match.team_a_host.id else f"Player {i+1}"
 team_a_text.append(f"{role}: {member.mention}")

 embed.add_field(
 name="■ Team A",
 value="\n".join(team_a_text),
 inline=True
 )

 # Team B
 team_b_text = []
 for i, member in enumerate(match.team_b):
 role = "■ Host" if member.id == match.team_b_host.id else f"Player {i+1}"
 team_b_text.append(f"{role}: {member.mention}")

 embed.add_field(
 name="■ Team B",
 value="\n".join(team_b_text),
 inline=True
 )

 return embed
def create_round_summary_embed(match, round_num: int) -> discord.Embed:
 """Create embed showing what each player should pick for a round"""
 embed = discord.Embed(
 title=f"■ Round {round_num} - Pick Phase",
 description=f"**Current Score:** {match.team_a_score}-{match.team_b_score}",
 color=discord.Color.gold()
 )

 pattern = match.get_round_pattern(round_num)

 # Team A assignments
 team_a_assignments = []
 for i, role in enumerate(pattern["team_a"]):
 player = match.team_a[i]
 pick = match.team_a_picks.get(i, "■ Not picked")
 emoji = "■■" if role == "killer" else "■"
 team_a_assignments.append(f"{emoji} {player.display_name}: {role.upper()} → {pick}")
 embed.add_field(
 name="■ Team A",
 value="\n".join(team_a_assignments),
 inline=False
 )

 # Team B assignments
 team_b_assignments = []
 for i, role in enumerate(pattern["team_b"]):
 player = match.team_b[i]
 pick = match.team_b_picks.get(i, "■ Not picked")
 emoji = "■■" if role == "killer" else "■"
 team_b_assignments.append(f"{emoji} {player.display_name}: {role.upper()} → {pick}")

 embed.add_field(
 name="■ Team B",
 value="\n".join(team_b_assignments),
 inline=False
 )

 embed.set_footer(text="Use /teampick to select your character!")

 return embed
def format_team_name(team: str) -> str:
 """Format team letter into display name"""
 return "Team A ■" if team == "A" else "Team B ■"
def get_opposite_team(team: str) -> str:
 """Get the opposite team"""
 return "B" if team == "A" else "A"
def validate_team_picks_complete(match) -> tuple[bool, str]:
 """
 Validate if all required picks for current round are complete
 Returns (is_complete, message)
 """
 pattern = match.get_round_pattern(match.current_round)

 # Check Team A
 team_a_needed = len(pattern["team_a"])
 team_a_current = len(match.team_a_picks)

 # Check Team B
 team_b_needed = len(pattern["team_b"])
 team_b_current = len(match.team_b_picks)

 if team_a_current < team_a_needed:
 missing = team_a_needed - team_a_current
 return False, f"Team A still needs {missing} pick(s)"

 if team_b_current < team_b_needed:
 missing = team_b_needed - team_b_current
 return False, f"Team B still needs {missing} pick(s)"

 return True, "All picks complete!"
def get_team_member_by_index(match, team: str, index: int) -> Optional[discord.Member]:
 """Get team member by their index"""
 members = match.team_a if team == "A" else match.team_b
 if 0 <= index < len(members):
 return members[index]
 return None
def create_match_progress_bar(match) -> str:
 """Create a visual progress bar for the match"""
 completed = match.rounds_completed
 total = match.total_rounds

 progress = int((completed / total) * 10)
 bar = "■" * progress + "■" * (10 - progress)

 return f"Progress: [{bar}] {completed}/{total} rounds"
def get_match_status_summary(match) -> str:
 """Get a one-line summary of match status"""
 if match.current_phase == "ban":
 return f"■ Ban Phase | Team A: {len(match.team_a_bans)}/{match.get_ban_limit()} | Team B: {len(match.team_b_bans)}/{mat elif match.current_phase == "pick":
 pattern = match.get_round_pattern(match.current_round)
 a_picks = len(match.team_a_picks)
 b_picks = len(match.team_b_picks)
 a_needed = len(pattern["team_a"])
 b_needed = len(pattern["team_b"])
 return f"■ Round {match.current_round} Pick Phase | Team A: {a_picks}/{a_needed} | Team B: {b_picks}/{b_needed}"
 elif match.current_phase == "results":
 a_claimed = "■" if match.team_a_claimed else "■"
 b_claimed = "■" if match.team_b_claimed else "■"
 return f"■ Waiting for Results | Team A: {a_claimed} | Team B: {b_claimed}"
 else:
 return "■ Unknown phase"
def create_tiebreaker_announcement_embed(match) -> discord.Embed:
 """Create dramatic tiebreaker announcement"""
 embed = discord.Embed(
 title="■■ TIEBREAKER ROUND!",
 description=f"The score is tied at **{match.team_a_score}-{match.team_b_score}**!\n\nThe final round will be played aga color=discord.Color.orange()
 )

 embed.add_field(
 name="■ Team A",
 value="\n".join([m.mention for m in match.team_a]),
 inline=True
 )

 embed.add_field(
 name="■ Team B",
 value="\n".join([m.mention for m in match.team_b]),
 inline=True
 )

 embed.set_footer(text="Winner takes all! Good luck!")

 return embed
def create_waiting_for_queue_embed(mode: str, party) -> discord.Embed:
 """Create embed for party waiting in queue"""
 embed = discord.Embed(
 title=f"■ {mode.upper()} Matchmaking",
 description=f"**{party.host.display_name}'s party** is searching for opponents!",
 color=discord.Color.blue()
 )

 members_text = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(party.members)])
 embed.add_field(
 name=f"Team ({party.get_size()} players)",
 value=members_text,
 inline=False
 )

 embed.add_field(
 name="Status",
 value="■ Waiting for another team...",
 inline=False
 )

 embed.set_footer(text="Use /cancelqueue to leave the queue")

 return embed
def get_mode_requirements_text(mode: str) -> str:
 """Get requirements text for a game mode"""
 requirements = {
 "2v2": "• 1-2 players in party\n• 1 ban per team\n• 4 rounds total",
 "3v3": "• 1-3 players in party\n• No bans\n• 6 rounds total",
 "4v4": "• 1-4 players in party\n• No bans\n• 8 rounds total"
 }
 return requirements.get(mode, "Unknown mode")
def calculate_estimated_match_time(mode: str) -> str:
 """Calculate estimated match duration"""
 times = {
 "2v2": "10-15 minutes",
 "3v3": "15-20 minutes",
 "4v4": "20-30 minutes"
 }
 return times.get(mode, "Unknown")
================================================================================
# FILE: team_matchmaking_part10.py (214 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 10
5v5 Tournament Mode
Host selects killer player and map each round, alternating between teams
"""
import discord
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
# Maps
MAPS = [
 "Glasshouses",
 "Pirate bay",
 "Brandonworks",
 "C00l Carnival",
 "Yorick's Resting Place",
 "Planet Voss",
 "Familiar Ruins",
 "Classic Battleground",
 "The Tempest",
 "Work At A Pizza Place"
]
# Map-specific killer recommendations (shown only to attacking team)
MAP_KILLER_RECOMMENDATIONS = {
 "Glasshouses": ["Nosferatu", "Guest 666"],
 "Pirate bay": ["C00lkidd"],
 "Brandonworks": ["Noli"], # Note: "Brandonworks" killer doesn't exist in KILLERS list
 "C00l Carnival": [],
 "Yorick's Resting Place": [],
 "Planet Voss": ["Slasher"],
 "Familiar Ruins": [],
 "Classic Battleground": ["C00lkidd"],
 "The Tempest": ["C00lkidd"],
 "Work At A Pizza Place": ["1x1x1x1"]
}
# Killer-specific ban recommendations (shown only to defending team)
KILLER_BAN_RECOMMENDATIONS = {
 "Slasher": {
 "solo": ["Elliot", "Builderman", "Two Time", "Veeronica"],
 "combo": [("Dusekkar", "Taph"), ("Chance", "Shedletsky")]
 },
 "Nosferatu": {
 "solo": ["Dusekkar", "Two Time", "Elliot", "007n7", "Guest 1337", "Taph"],
 "combo": []
 },
 "C00lkidd": {
 "solo": ["Guest 1337", "Elliot", "Builderman", "Chance", "Two Time"],
 "combo": [("Dusekkar", "Taph")]
 },
 "John Doe": {
 "solo": ["Elliot", "Two Time", "Veeronica", "Chance", "Shedletsky"],
 "combo": [("Dusekkar", "Taph")]
 },
 "Guest 666": {
 "solo": ["Guest 1337", "Shedletsky", "Two Time", "Chance"],
 "combo": [("Dusekkar", "Taph"), ("Elliot", "007n7")]
 },
 "1x1x1x1": {
 "solo": ["Guest 1337", "Builderman", "Veeronica", "Two Time"],
 "combo": [("Elliot", "Dusekkar"), ("Shedletsky", "Chance")]
 },
 "Noli": {
 "solo": ["Guest 1337", "Elliot", "Taph", "Shedletsky", "Dusekkar", "Builderman", "007n7"],
 "combo": []
 }
}
# 5v5 Tournament Constants
TOURNAMENT_ROUNDS = 10
TOURNAMENT_WIN_POINTS = 10 # Points for winning team
TOURNAMENT_LOSS_POINTS = -10 # Points for losing team
MAX_SURVIVOR_BANS = 2 # 2 bans per defending team
class Tournament5v5Match:
 """Represents a 5v5 tournament match"""
 def __init__(self, team_a: List[discord.Member], team_b: List[discord.Member],
 channel: discord.TextChannel):
 self.team_a = team_a # List of 5 members
 self.team_b = team_b
 self.team_a_host = team_a[0] # Host is always first member
 self.team_b_host = team_b[0]
 self.channel = channel
 self.thread: Optional[discord.Thread] = None

 # Match state
 self.current_round = 1
 self.current_phase = "map_select" # "map_select", "killer_select", "ban", "pick", "results"
 self.attacking_team = "A" # Team that has the killer this round

 # Round tracking
 self.selected_map: Optional[str] = None
 self.selected_killer_player_index: Optional[int] = None # Which player (0-4) is killer
 self.selected_killer_character: Optional[str] = None # Which killer character
 self.banned_survivors: List[str] = [] # Survivors banned by defending team

 # Survivor picks (defending team) - player_index -> character
 self.round_survivor_picks: Dict[int, str] = {}

 # Match scoring
 self.team_a_score = 0
 self.team_b_score = 0
 self.rounds_completed = 0
 self.team_a_claimed: Optional[str] = None
 self.team_b_claimed: Optional[str] = None
 self.match_complete = False

 # Status tracking
 self.status_message: Optional[discord.Message] = None
 self.history: List[Dict] = [] # Store round history

 def get_attacking_team(self) -> str:
 """Get which team is attacking (has killer) this round"""
 # Alternates: Round 1=A, 2=B, 3=A, 4=B, etc.
 return "A" if self.current_round % 2 == 1 else "B"

 def get_defending_team(self) -> str:
 """Get which team is defending (all survivors) this round"""
 return "B" if self.attacking_team == "A" else "A"

 def get_attacking_host(self) -> discord.Member:
 """Get host of attacking team"""
 return self.team_a_host if self.attacking_team == "A" else self.team_b_host

 def get_defending_host(self) -> discord.Member:
 """Get host of defending team"""
 return self.team_b_host if self.attacking_team == "A" else self.team_a_host

 def get_team_members(self, team: str) -> List[discord.Member]:
 """Get members of a team"""
 return self.team_a if team == "A" else self.team_b
 def get_team_host(self, team: str) -> discord.Member:
 """Get host of a team"""
 return self.team_a_host if team == "A" else self.team_b_host

 def is_team_host(self, user: discord.Member) -> Optional[str]:
 """Check if user is a team host, return team letter or None"""
 if user.id == self.team_a_host.id:
 return "A"
 elif user.id == self.team_b_host.id:
 return "B"
 return None

 def get_user_team(self, user: discord.Member) -> Optional[str]:
 """Get which team a user is on"""
 if user.id in [m.id for m in self.team_a]:
 return "A"
 elif user.id in [m.id for m in self.team_b]:
 return "B"
 return None

 def reset_round_state(self):
 """Reset state for next round"""
 self.selected_map = None
 self.selected_killer_player_index = None
 self.selected_killer_character = None
 self.banned_survivors.clear()
 self.round_survivor_picks.clear()
 self.current_phase = "map_select"
 self.attacking_team = self.get_attacking_team()

 def get_available_survivors_for_pick(self) -> List[str]:
 """Get survivors available for defending team to pick"""
 available = []
 for survivor in SURVIVORS:
 # Not banned and not already picked
 if survivor not in self.banned_survivors and survivor not in self.round_survivor_picks.values():
 available.append(survivor)
 return available

 def is_picks_complete(self) -> bool:
 """Check if all 5 defending players have picked survivors"""
 return len(self.round_survivor_picks) >= 5

 def save_round_history(self):
 """Save completed round to history"""
 defending_team = self.get_defending_team()
 defending_members = self.get_team_members(defending_team)

 survivor_picks_formatted = []
 for i in range(5):
 player = defending_members[i]
 survivor = self.round_survivor_picks.get(i, "None")
 survivor_picks_formatted.append(f"{player.display_name}: {survivor}")

 killer_player = self.get_team_members(self.attacking_team)[self.selected_killer_player_index]

 round_data = {
 "round": self.rounds_completed,
 "map": self.selected_map,
 "attacking_team": self.attacking_team,
 "killer_player": killer_player.display_name,
 "killer_character": self.selected_killer_character,
 "bans": list(self.banned_survivors),
 "defender_picks": survivor_picks_formatted,
 "winner": "A" if self.team_a_claimed == "win" else "B"
 }

 self.history.append(round_data)
================================================================================
# FILE: team_matchmaking_part11.py (293 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 11
5v5 Tournament Matchmaking & Game Flow
Handles /challenge system and phase progression
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
 self.pending_challenges: Dict[int, int] = {} # challenger_host_id -> challenged_host_id
 self.active_matches: Dict[int, Tournament5v5Match] = {} # thread_id -> Match
 self.ALLOWED_CHANNEL_ID = 1465526001110093834

 async def send_challenge(self, interaction: discord.Interaction, opponent: discord.Member):
 """Host challenges another party host to 5v5"""
 # Check channel
 if interaction.channel_id != self.ALLOWED_CHANNEL_ID:
 await interaction.response.send_message(
 f"■ 5v5 can only be used in <#{self.ALLOWED_CHANNEL_ID}>!",
 ephemeral=True
 )
 return

 user = interaction.user

 # Check if user has a party
 party = self.party_system.get_user_party(user)
 if not party:
 await interaction.response.send_message("■ You need a party first! Use `/party`", ephemeral=True)
 return

 # Must be host
 if not party.is_host(user):
 await interaction.response.send_message("■ Only party host can challenge!", ephemeral=True)
 return

 # Party must have exactly 5 members
 if party.get_size() != 5:
 await interaction.response.send_message(
 f"■ You need exactly 5 members for 5v5! (Current: {party.get_size()})",
 ephemeral=True
 )
 return

 # Check opponent has a party
 opponent_party = self.party_system.get_user_party(opponent)
 if not opponent_party:
 await interaction.response.send_message(f"■ {opponent.mention} doesn't have a party!", ephemeral=True)
 return

 if not opponent_party.is_host(opponent):
 await interaction.response.send_message(f"■ {opponent.mention} is not a party host!", ephemeral=True)
 return

 if opponent_party.get_size() != 5:
 await interaction.response.send_message(
 f"■ {opponent.mention}'s party needs exactly 5 members! (Current: {opponent_party.get_size()})",
 ephemeral=True
 )
 return

 # Can't challenge yourself
 if user.id == opponent.id:
 await interaction.response.send_message("■ You can't challenge yourself!", ephemeral=True)
 return

 # Check if already in a match
 for match in self.active_matches.values():
 if user.id in [m.id for m in match.team_a + match.team_b]:
 await interaction.response.send_message("■ You're already in a 5v5 match!", ephemeral=True)
 return
 # Send challenge
 self.pending_challenges[user.id] = opponent.id

 embed = discord.Embed(
 title="■■ 5v5 TOURNAMENT CHALLENGE!",
 description=f"**{user.mention}** challenges **{opponent.mention}** to a 5v5 tournament!",
 color=discord.Color.orange()
 )

 # Show both teams
 team_a_text = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(party.members)])
 team_b_text = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(opponent_party.members)])

 embed.add_field(name="■ Team A (Challenger)", value=team_a_text, inline=True)
 embed.add_field(name="■ Team B (Challenged)", value=team_b_text, inline=True)
 embed.add_field(
 name="Format",
 value="**10 rounds** | Best of 10 wins\nHosts select maps and killer players",
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
 f"■ No pending challenge from {challenger.mention}!",
 ephemeral=True
 )
 return

 if self.pending_challenges[challenger.id] != user.id:
 await interaction.response.send_message(
 f"■ {challenger.mention} didn't challenge you!",
 ephemeral=True
 )
 return

 # Get parties
 challenger_party = self.party_system.get_user_party(challenger)
 accepter_party = self.party_system.get_user_party(user)

 if not challenger_party or not accepter_party:
 await interaction.response.send_message("■ One of the parties no longer exists!", ephemeral=True)
 del self.pending_challenges[challenger.id]
 return

 # Verify sizes
 if challenger_party.get_size() != 5 or accepter_party.get_size() != 5:
 await interaction.response.send_message("■ Both parties must have exactly 5 members!", ephemeral=True)
 del self.pending_challenges[challenger.id]
 return

 # Create match
 await self.create_tournament_match(
 interaction,
 list(challenger_party.members),
 list(accepter_party.members)
 )

 # Remove challenge
 del self.pending_challenges[challenger.id]

 async def create_tournament_match(self, interaction: discord.Interaction,
 team_a: list, team_b: list):
 """Create a 5v5 tournament match"""
 match = Tournament5v5Match(team_a, team_b, interaction.channel)

 # Create embed
 embed = discord.Embed(
 title="■■ 5v5 TOURNAMENT STARTING!",
 description="**10 rounds** of intense 1v5 combat!",
 color=discord.Color.gold()
 )
 team_a_text = "\n".join([f"{i+1}. {m.mention} {'■' if i == 0 else ''}" for i, m in enumerate(team_a)])
 team_b_text = "\n".join([f"{i+1}. {m.mention} {'■' if i == 0 else ''}" for i, m in enumerate(team_b)])

 embed.add_field(name="■ Team A", value=team_a_text, inline=True)
 embed.add_field(name="■ Team B", value=team_b_text, inline=True)

 await interaction.response.send_message(embed=embed)
 message = await interaction.original_response()

 # Create thread
 thread = await message.create_thread(
 name=f"■■ 5v5 TOURNAMENT: {team_a[0].display_name} vs {team_b[0].display_name}",
 auto_archive_duration=120
 )

 match.thread = thread
 self.active_matches[thread.id] = match

 # Start first round
 await self.start_round(match)

 async def start_round(self, match: Tournament5v5Match):
 """Start a new round"""
 thread = match.thread

 match.attacking_team = match.get_attacking_team()
 attacking_host = match.get_attacking_host()
 defending_host = match.get_defending_host()

 # Announce round
 embed = discord.Embed(
 title=f"■ ROUND {match.current_round}/10",
 description=f"**Score:** {match.team_a_score} - {match.team_b_score}",
 color=discord.Color.blue()
 )

 attacking_team_name = "Team A ■" if match.attacking_team == "A" else "Team B ■"
 defending_team_name = "Team B ■" if match.attacking_team == "A" else "Team A ■"

 embed.add_field(
 name="■■ Attacking (Killer)",
 value=f"{attacking_team_name}\nHost: {attacking_host.mention}",
 inline=True
 )
 embed.add_field(
 name="■■ Defending (Survivors)",
 value=f"{defending_team_name}\nHost: {defending_host.mention}",
 inline=True
 )
 embed.add_field(
 name="■ Phase 1: Map Selection",
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
 title=f"■ Round {match.current_round} Status",
 color=discord.Color.gold()
 )
 # Phase indicator
 phase_text = {
 "map_select": "■■ MAP SELECTION",
 "killer_select": "■■ KILLER SELECTION",
 "ban": "■ BAN PHASE",
 "pick": "■ PICK PHASE",
 "results": "■ AWAITING RESULTS"
 }.get(match.current_phase, "Unknown")

 embed.description = f"**Phase:** {phase_text}\n**Score:** {match.team_a_score}-{match.team_b_score}"

 # Show round info
 if match.selected_map:
 embed.add_field(name="■■ Map", value=match.selected_map, inline=True)

 if match.selected_killer_character:
 attacking_members = match.get_team_members(match.attacking_team)
 killer_player = attacking_members[match.selected_killer_player_index]
 embed.add_field(
 name="■■ Killer",
 value=f"{killer_player.mention}\n{match.selected_killer_character}",
 inline=True
 )

 if match.banned_survivors:
 embed.add_field(
 name="■ Banned Survivors",
 value=", ".join(match.banned_survivors),
 inline=False
 )

 if match.round_survivor_picks:
 defending_members = match.get_team_members(match.get_defending_team())
 picks_text = []
 for i in range(5):
 player = defending_members[i]
 pick = match.round_survivor_picks.get(i, "■")
 picks_text.append(f"{i+1}. {player.display_name}: {pick}")

 embed.add_field(
 name="■ Survivor Picks",
 value="\n".join(picks_text),
 inline=False
 )

 return embed
================================================================================
# FILE: team_matchmaking_part12.py (324 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 12
5v5 Tournament Game Commands
Map selection, killer selection, banning, and picking phases
"""
import discord
from discord import app_commands
from team_matchmaking_part10 import (
 MAPS, KILLERS, SURVIVORS,
 MAP_KILLER_RECOMMENDATIONS,
 KILLER_BAN_RECOMMENDATIONS,
 MAX_SURVIVOR_BANS
)
class Tournament5v5GameLogic:
 """Game logic for 5v5 tournament"""

 @staticmethod
 async def handle_map_select(interaction: discord.Interaction, tournament_system, map_name: str):
 """Attacking team host selects map"""
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return
 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Check phase
 if match.current_phase != "map_select":
 await interaction.response.send_message("■ Not in map selection phase!", ephemeral=True)
 return

 # Must be attacking team host
 user_team = match.is_team_host(user)
 if user_team != match.attacking_team:
 await interaction.response.send_message(
 f"■ Only {match.get_attacking_host().mention} (attacking host) can select map!",
 ephemeral=True
 )
 return

 # Validate map
 if map_name not in MAPS:
 await interaction.response.send_message(f"■ Invalid map: {map_name}", ephemeral=True)
 return

 # Set map
 match.selected_map = map_name
 match.current_phase = "killer_select"

 # Announce map
 await interaction.response.send_message(
 f"■■ **Map selected:** {map_name}",
 ephemeral=False
 )

 # Show killer recommendations to attacking team
 recommendations = MAP_KILLER_RECOMMENDATIONS.get(map_name, [])
 if recommendations:
 rec_text = ", ".join(recommendations)
 attacking_members = match.get_team_members(match.attacking_team)
 mentions = " ".join([m.mention for m in attacking_members])

 await match.thread.send(
 f"■ {mentions}\n**Recommended killers for {map_name}:** {rec_text}",
 )

 # Next phase
 await match.thread.send(
 f"■■ **Phase 2: Killer Selection**\n"
 f"{match.get_attacking_host().mention} use `/selectkiller <player_number> <killer>` "
 f"to choose which player will be killer!"
 )

 await tournament_system.update_status_message(match)

 @staticmethod
 async def handle_killer_select(interaction: discord.Interaction, tournament_system,
 player_number: int, killer: str):
 """Attacking team host selects which player will be killer and which killer character"""
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return

 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Check phase
 if match.current_phase != "killer_select":
 await interaction.response.send_message("■ Not in killer selection phase!", ephemeral=True)
 return

 # Must be attacking team host
 user_team = match.is_team_host(user)
 if user_team != match.attacking_team:
 await interaction.response.send_message("■ Only attacking host can select killer!", ephemeral=True)
 return

 # Validate player number (1-5)
 if player_number < 1 or player_number > 5:
 await interaction.response.send_message("■ Player number must be 1-5!", ephemeral=True)
 return
 # Validate killer
 if killer not in KILLERS:
 await interaction.response.send_message(f"■ Invalid killer: {killer}", ephemeral=True)
 return

 # Set killer
 player_index = player_number - 1
 match.selected_killer_player_index = player_index
 match.selected_killer_character = killer
 match.current_phase = "ban"

 # Get player
 attacking_members = match.get_team_members(match.attacking_team)
 killer_player = attacking_members[player_index]

 # Announce
 await interaction.response.send_message(
 f"■■ **Killer selected:** Player {player_number} ({killer_player.mention}) will play as **{killer}**!",
 ephemeral=False
 )

 # Show ban recommendations to defending team ONLY
 ban_recs = KILLER_BAN_RECOMMENDATIONS.get(killer, {})
 if ban_recs.get("solo") or ban_recs.get("combo"):
 defending_members = match.get_team_members(match.get_defending_team())
 mentions = " ".join([m.mention for m in defending_members])

 solo_bans = ", ".join(ban_recs.get("solo", []))
 combo_bans = " OR ".join([f"{a} + {b}" for a, b in ban_recs.get("combo", [])])

 rec_text = f"**Ban Recommendations vs {killer}:**\n"
 if solo_bans:
 rec_text += f"• **Solo Bans:** {solo_bans}\n"
 if combo_bans:
 rec_text += f"• **Combo Bans:** {combo_bans}"

 await match.thread.send(f"■ {mentions}\n{rec_text}")

 # Next phase
 await match.thread.send(
 f"■ **Phase 3: Ban Phase**\n"
 f"{match.get_defending_host().mention} use `/tournamentban <survivor>` to ban survivors! "
 f"(Max 2 bans)"
 )

 await tournament_system.update_status_message(match)

 @staticmethod
 async def handle_tournament_ban(interaction: discord.Interaction, tournament_system, survivor: str):
 """Defending team host bans survivors"""
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return

 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Check phase
 if match.current_phase != "ban":
 await interaction.response.send_message("■ Not in ban phase!", ephemeral=True)
 return

 # Must be defending team host
 defending_team = match.get_defending_team()
 user_team = match.is_team_host(user)
 if user_team != defending_team:
 await interaction.response.send_message("■ Only defending host can ban!", ephemeral=True)
 return

 # Check ban limit
 if len(match.banned_survivors) >= MAX_SURVIVOR_BANS:
 await interaction.response.send_message(f"■ Already banned {MAX_SURVIVOR_BANS} survivors!", ephemeral=True)
 return

 # Validate survivor
 if survivor not in SURVIVORS:
 await interaction.response.send_message(f"■ Invalid survivor: {survivor}", ephemeral=True)
 return
 # Check if already banned
 if survivor in match.banned_survivors:
 await interaction.response.send_message(f"■ {survivor} is already banned!", ephemeral=True)
 return

 # Add ban
 match.banned_survivors.append(survivor)

 # Announce
 defending_team_name = "Team A ■" if defending_team == "A" else "Team B ■"
 await interaction.response.send_message(
 f"■ **{defending_team_name}** banned **{survivor}**! ({len(match.banned_survivors)}/{MAX_SURVIVOR_BANS})",
 ephemeral=False
 )

 # Check if bans complete
 if len(match.banned_survivors) >= MAX_SURVIVOR_BANS:
 match.current_phase = "pick"
 await match.thread.send(
 f"■ **Phase 4: Pick Phase**\n"
 f"Defending team, use `/tournamentpick <survivor>` to pick your survivors!\n"
 f"Each of the 5 players must pick a unique survivor."
 )

 await tournament_system.update_status_message(match)

 @staticmethod
 async def handle_tournament_pick(interaction: discord.Interaction, tournament_system, survivor: str):
 """Defending team players pick their survivors"""
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return

 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Check phase
 if match.current_phase != "pick":
 await interaction.response.send_message("■ Not in pick phase!", ephemeral=True)
 return

 # Must be on defending team
 defending_team = match.get_defending_team()
 user_team = match.get_user_team(user)
 if user_team != defending_team:
 await interaction.response.send_message("■ Only defending team can pick!", ephemeral=True)
 return

 # Get player index
 defending_members = match.get_team_members(defending_team)
 user_index = None
 for i, member in enumerate(defending_members):
 if member.id == user.id:
 user_index = i
 break

 if user_index is None:
 await interaction.response.send_message("■ Could not find your position!", ephemeral=True)
 return

 # Check if already picked
 if user_index in match.round_survivor_picks:
 await interaction.response.send_message(
 f"■ You already picked {match.round_survivor_picks[user_index]}!",
 ephemeral=True
 )
 return

 # Validate survivor
 if survivor not in SURVIVORS:
 await interaction.response.send_message(f"■ Invalid survivor: {survivor}", ephemeral=True)
 return

 # Check if banned
 if survivor in match.banned_survivors:
 await interaction.response.send_message(f"■ {survivor} is banned!", ephemeral=True)
 return
 # Check if already picked by team
 if survivor in match.round_survivor_picks.values():
 await interaction.response.send_message(f"■ {survivor} already picked by teammate!", ephemeral=True)
 return

 # Add pick
 match.round_survivor_picks[user_index] = survivor

 # Announce
 defending_team_name = "Team A ■" if defending_team == "A" else "Team B ■"
 await interaction.response.send_message(
 f"■ **{defending_team_name}** {user.mention} picked **{survivor}**! "
 f"({len(match.round_survivor_picks)}/5)",
 ephemeral=False
 )

 # Check if all picks complete
 if match.is_picks_complete():
 match.current_phase = "results"
 await match.thread.send(
 f"■ **ROUND {match.current_round} READY!**\n"
 f"Play the round now!\n"
 f"After completion, hosts use `/tournamentwon` or `/tournamentloss` to report results."
 )

 await tournament_system.update_status_message(match)

 @staticmethod
 def get_map_autocomplete(current: str):
 """Autocomplete for map selection"""
 filtered = [m for m in MAPS if current.lower() in m.lower()] if current else MAPS
 return [app_commands.Choice(name=m, value=m) for m in filtered[:25]]

 @staticmethod
 def get_killer_autocomplete(current: str):
 """Autocomplete for killer selection"""
 filtered = [k for k in KILLERS if current.lower() in k.lower()] if current else KILLERS
 return [app_commands.Choice(name=k, value=k) for k in filtered[:25]]

 @staticmethod
 def get_survivor_ban_autocomplete(match, current: str):
 """Autocomplete for survivor bans"""
 available = [s for s in SURVIVORS if s not in match.banned_survivors]
 if current:
 available = [s for s in available if current.lower() in s.lower()]
 return [app_commands.Choice(name=s, value=s) for s in available[:25]]

 @staticmethod
 def get_survivor_pick_autocomplete(match, current: str):
 """Autocomplete for survivor picks"""
 available = match.get_available_survivors_for_pick()
 if current:
 available = [s for s in available if current.lower() in s.lower()]
 return [app_commands.Choice(name=s, value=s) for s in available[:25]]
================================================================================
# FILE: team_matchmaking_part13.py (288 lines)
================================================================================
"""
TEAM MATCHMAKING SYSTEM - PART 13
5v5 Tournament Results & Command Setup
Handles match results, scoring, and slash command registration
"""
import discord
from discord import app_commands
from typing import Optional
from team_matchmaking_part10 import TOURNAMENT_WIN_POINTS, TOURNAMENT_LOSS_POINTS
class Tournament5v5Results:
 """Handle 5v5 tournament match results"""

 @staticmethod
 async def handle_tournament_result(interaction: discord.Interaction, tournament_system,
 multi_mode_stats, result: str):
 """Handle tournament round result reporting"""
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return

 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Check phase
 if match.current_phase != "results":
 await interaction.response.send_message("■ Complete the pick phase first!", ephemeral=True)
 return

 # Must be a team host
 user_team = match.is_team_host(user)
 if not user_team:
 await interaction.response.send_message("■ Only team hosts can report results!", ephemeral=True)
 return

 # Record claim
 if user_team == "A":
 if match.team_a_claimed:
 await interaction.response.send_message("■ Your team already reported!", ephemeral=True)
 return
 match.team_a_claimed = result
 else:
 if match.team_b_claimed:
 await interaction.response.send_message("■ Your team already reported!", ephemeral=True)
 return
 match.team_b_claimed = result

 # Check if both reported
 if match.team_a_claimed and match.team_b_claimed:
 # Validate
 valid = (
 (match.team_a_claimed == "win" and match.team_b_claimed == "loss") or
 (match.team_a_claimed == "loss" and match.team_b_claimed == "win")
 )

 if not valid:
 await interaction.response.send_message(
 "■ **Results don't match!** Please verify who won this round.",
 ephemeral=False
 )
 match.team_a_claimed = None
 match.team_b_claimed = None
 return

 # Update scores
 if match.team_a_claimed == "win":
 match.team_a_score += 1
 else:
 match.team_b_score += 1

 # Save round to history
 match.save_round_history()
 match.rounds_completed += 1

 # Reset for next round
 match.team_a_claimed = None
 match.team_b_claimed = None

 # Check if match is over (10 rounds or someone has 6+ wins)
 match_over = (
 match.rounds_completed >= 10 or
 match.team_a_score >= 6 or
 match.team_b_score >= 6
 )

 if match_over:
 # Match complete!
 await Tournament5v5Results.finalize_tournament(
 interaction, tournament_system, multi_mode_stats, match
 )
 else:
 # Next round
 match.current_round += 1
 match.reset_round_state()
 await interaction.response.send_message(
 f"■ **Round {match.rounds_completed} Complete!**\n"
 f"**Score:** {match.team_a_score}-{match.team_b_score}\n"
 f"Starting Round {match.current_round}...",
 ephemeral=False
 )

 # Start next round
 await tournament_system.start_round(match)

 else:
 # Waiting for other host
 other_team = "B" if user_team == "A" else "A"
 other_host = match.get_team_host(other_team)
 await interaction.response.send_message(
 f"■ Team {user_team} reported a **{result}**.\n"
 f"Waiting for {other_host.mention} (Team {other_team}) to report...",
 ephemeral=False
 )

 @staticmethod
 async def finalize_tournament(interaction, tournament_system, multi_mode_stats, match):
 """Finalize tournament and award points"""
 # Determine winner
 if match.team_a_score > match.team_b_score:
 winning_team = match.team_a
 losing_team = match.team_b
 winner_name = "Team A ■"
 loser_name = "Team B ■"
 else:
 winning_team = match.team_b
 losing_team = match.team_a
 winner_name = "Team B ■"
 loser_name = "Team A ■"

 # Award points to all team members
 for member in winning_team:
 stats = multi_mode_stats.get_or_create_stats(member, "5v5")
 stats.points += TOURNAMENT_WIN_POINTS
 stats.wins += 1

 for member in losing_team:
 stats = multi_mode_stats.get_or_create_stats(member, "5v5")
 stats.points = max(0, stats.points + TOURNAMENT_LOSS_POINTS)
 stats.losses += 1

 multi_mode_stats.save_stats()

 # Create final embed
 embed = discord.Embed(
 title="■ 5v5 TOURNAMENT COMPLETE!",
 description=f"**{winner_name}** wins the tournament!",
 color=discord.Color.gold()
 )
 embed.add_field(
 name="Final Score",
 value=f"```\n{match.team_a_score}-{match.team_b_score}\n```",
 inline=False
 )
 embed.add_field(
 name="Points",
 value=f"**{winner_name}:** +{TOURNAMENT_WIN_POINTS} points each\n"
 f"**{loser_name}:** {TOURNAMENT_LOSS_POINTS} points each",
 inline=False
 )
 embed.add_field(
 name="Rounds Played",
 value=f"{match.rounds_completed}/10 rounds",
 inline=False
 )

 await interaction.response.send_message(embed=embed)

 # Clean up
 del tournament_system.active_matches[match.thread.id]

 # Archive thread
 await match.thread.edit(archived=True)
def setup_5v5_tournament_commands(tree: app_commands.CommandTree, tournament_system, multi_mode_stats):
 """Setup all 5v5 tournament commands"""

 from team_matchmaking_part12 import Tournament5v5GameLogic

 @tree.command(name="challenge", description="Challenge another party host to a 5v5 tournament")
 @app_commands.describe(opponent="Party host to challenge")
 async def challenge_5v5(interaction: discord.Interaction, opponent: discord.Member):
 await tournament_system.send_challenge(interaction, opponent)

 @tree.command(name="acceptchallenge", description="Accept a 5v5 tournament challenge")
 @app_commands.describe(challenger="Party host who challenged you")
 async def accept_challenge_5v5(interaction: discord.Interaction, challenger: discord.Member):
 await tournament_system.accept_challenge(interaction, challenger)

 @tree.command(name="selectmap", description="[5v5] Select map for the round (attacking host)")
 @app_commands.describe(map_name="Map to play on")
 async def select_map(interaction: discord.Interaction, map_name: str):
 await Tournament5v5GameLogic.handle_map_select(interaction, tournament_system, map_name)

 @select_map.autocomplete('map_name')
 async def map_autocomplete(interaction: discord.Interaction, current: str):
 return Tournament5v5GameLogic.get_map_autocomplete(current)

 @tree.command(name="selectkiller", description="[5v5] Select killer player and character (attacking host)")
 @app_commands.describe(
 player_number="Which player will be killer (1-5)",
 killer="Killer character"
 )
 async def select_killer(interaction: discord.Interaction, player_number: int, killer: str):
 await Tournament5v5GameLogic.handle_killer_select(interaction, tournament_system, player_number, killer)

 @select_killer.autocomplete('killer')
 async def killer_autocomplete(interaction: discord.Interaction, current: str):
 return Tournament5v5GameLogic.get_killer_autocomplete(current)

 @tree.command(name="tournamentban", description="[5v5] Ban a survivor (defending host)")
 @app_commands.describe(survivor="Survivor to ban")
 async def tournament_ban(interaction: discord.Interaction, survivor: str):
 await Tournament5v5GameLogic.handle_tournament_ban(interaction, tournament_system, survivor)

 @tournament_ban.autocomplete('survivor')
 async def ban_survivor_autocomplete(interaction: discord.Interaction, current: str):
 thread_id = interaction.channel_id
 if thread_id not in tournament_system.active_matches:
 return []
 match = tournament_system.active_matches[thread_id]
 return Tournament5v5GameLogic.get_survivor_ban_autocomplete(match, current)

 @tree.command(name="tournamentpick", description="[5v5] Pick your survivor (defending team)")
 @app_commands.describe(survivor="Survivor to pick")
 async def tournament_pick(interaction: discord.Interaction, survivor: str):
 await Tournament5v5GameLogic.handle_tournament_pick(interaction, tournament_system, survivor)

 @tournament_pick.autocomplete('survivor')
 async def pick_survivor_autocomplete(interaction: discord.Interaction, current: str):
 thread_id = interaction.channel_id
 if thread_id not in tournament_system.active_matches:
 return []
 match = tournament_system.active_matches[thread_id]
 return Tournament5v5GameLogic.get_survivor_pick_autocomplete(match, current)

 @tree.command(name="tournamentwon", description="[5v5] Report your team won the round (host only)")
 async def tournament_won(interaction: discord.Interaction):
 await Tournament5v5Results.handle_tournament_result(
 interaction, tournament_system, multi_mode_stats, "win"
 )

 @tree.command(name="tournamentloss", description="[5v5] Report your team lost the round (host only)")
 async def tournament_loss(interaction: discord.Interaction):
 await Tournament5v5Results.handle_tournament_result(
 interaction, tournament_system, multi_mode_stats, "loss"
 )

 @tree.command(name="tournamentcancel", description="[5v5] Cancel tournament (host only, no penalty)")
 async def tournament_cancel(interaction: discord.Interaction):
 thread_id = interaction.channel_id

 if thread_id not in tournament_system.active_matches:
 await interaction.response.send_message("■ No active 5v5 match!", ephemeral=True)
 return

 match = tournament_system.active_matches[thread_id]
 user = interaction.user

 # Must be a team host
 team = match.is_team_host(user)
 if not team:
 await interaction.response.send_message("■ Only team hosts can cancel!", ephemeral=True)
 return

 embed = discord.Embed(
 title="■ 5v5 Tournament Cancelled",
 description=f"Tournament cancelled by {user.mention} (Team {team} Host)",
 color=discord.Color.red()
 )
 embed.add_field(
 name="Result",
 value="No points affected. Tournament ended without completion.",
 inline=False
 )

 await interaction.response.send_message(embed=embed)

 # Clean up
 del tournament_system.active_matches[thread_id]
 await match.thread.edit(archived=True)

 return tournament_system
================================================================================
# FILE: team_matchmaking_part14.py (345 lines)
================================================================================
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
 self.banner_url: Optional[str] = None # Discord CDN link
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
 print(f"■ Loaded {len(self.profiles)} player profiles")
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
 title=f"■ {user.display_name}'s Profile",
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
 name="■ Bio",
 value=f"```\n{profile.bio}\n```",
 inline=False
 )

 # Mains section
 mains_text = ""
 if profile.main_killer:
 mains_text += f"■■ **Killer Main:** {profile.main_killer}\n"
 if profile.main_survivor:
 mains_text += f"■ **Survivor Main:** {profile.main_survivor}\n"

 if mains_text:
 embed.add_field(
 name="■ Mains",
 value=mains_text,
 inline=False
 )

 # Detailed stats section
 stats_text = f"■■ **Playtime:** {profile.playtime_hours} hours\n"
 stats_text += f"■■ **Killer Wins:** {profile.killer_wins}\n"
 stats_text += f"■ **Survivor Wins:** {profile.survivor_wins}\n"

 embed.add_field(
 name="■ Detailed Stats",
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
 name="■ Mode Stats",
 value="\n".join(mode_summary),
 inline=True
 )

 # Footer with last update
 embed.set_footer(text=f"Profile last updated: {profile.last_updated.strftime('%Y-%m-%d')}")

 return embed
def create_simple_profile_card(user: discord.Member, profile: PlayerProfile) -> str:
 """Create ASCII art profile card for text display"""

 card = f"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
■ ■ {user.display_name.center(42)} ■
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
■ ■
"""

 if profile.bio:
 bio_lines = textwrap.wrap(profile.bio, width=45)
 for line in bio_lines[:3]: # Max 3 lines
 card += f"■ {line.ljust(47)} ■\n"
 card += "■ ■\n"

 card += "■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■\n"

 if profile.main_killer:
 card += f"■ ■■ Killer Main: {profile.main_killer.ljust(31)} ■\n"
 if profile.main_survivor:
 card += f"■ ■ Survivor Main: {profile.main_survivor.ljust(29)} ■\n"

 card += "■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■\n"
 card += f"■ ■■ Playtime: {str(profile.playtime_hours).ljust(34)} hours ■\n"
 card += f"■ ■■ Killer Wins: {str(profile.killer_wins).ljust(32)} ■\n"
 card += f"■ ■ Survivor Wins: {str(profile.survivor_wins).ljust(29)} ■\n"
 card += "■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■"

 return card
async def handle_profile_banner_set(interaction: discord.Interaction, profile_system: ProfileSystem,
 banner_url: str):
 """Set profile banner"""
 profile = profile_system.get_or_create_profile(interaction.user)

 # Validate URL
 if not profile_system.validate_banner_url(banner_url):
 await interaction.response.send_message(
 "■ Please use a Discord CDN link (cdn.discordapp.com or media.discordapp.net)\n"
 "Upload an image in Discord, then right-click → Copy Link",
 ephemeral=True
 )
 return

 # Test if URL is accessible
 try:
 response = requests.head(banner_url, timeout=5)
 if response.status_code != 200:
 await interaction.response.send_message(
 "■ Unable to access that image URL. Make sure it's a valid Discord CDN link.",
 ephemeral=True
 )
 return
 except:
 await interaction.response.send_message(
 "■ Unable to access that image URL. Make sure it's a valid Discord CDN link.",
 ephemeral=True
 )
 return

 profile.banner_url = banner_url
 profile.last_updated = datetime.now()
 profile_system.save_profiles()

 await interaction.response.send_message(
 "■ Profile banner updated! View it with `/stats`",
 ephemeral=False
 )
async def handle_profile_bio_set(interaction: discord.Interaction, profile_system: ProfileSystem,
 bio: str):
 """Set profile bio"""
 profile = profile_system.get_or_create_profile(interaction.user)

 # Limit bio length
 if len(bio) > 200:
 await interaction.response.send_message(
 f"■ Bio too long! Maximum 200 characters. (Current: {len(bio)})",
 ephemeral=True
 )
 return

 profile.bio = bio
 profile.last_updated = datetime.now()
 profile_system.save_profiles()

 await interaction.response.send_message(
 "■ Profile bio updated! View it with `/stats`",
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
 f"■ Invalid killer: {character_name}\nAvailable: {', '.join(KILLERS)}",
 ephemeral=True
 )
 return
 profile.main_killer = character_name
 message = f"■ Killer main set to **{character_name}**!"
 else: # survivor
 if character_name not in SURVIVORS:
 await interaction.response.send_message(
 f"■ Invalid survivor: {character_name}\nAvailable: {', '.join(SURVIVORS)}",
 ephemeral=True
 )
 return
 profile.main_survivor = character_name
 message = f"■ Survivor main set to **{character_name}**!"

 profile.last_updated = datetime.now()
 profile_system.save_profiles()

 await interaction.response.send_message(message, ephemeral=False)
async def handle_profile_stats_set(interaction: discord.Interaction, profile_system: ProfileSystem,
 stat_type: str, value: int):
 """Set playtime, killer wins, or survivor wins"""
 profile = profile_system.get_or_create_profile(interaction.user)

 if value < 0:
 await interaction.response.send_message("■ Value cannot be negative!", ephemeral=True)
 return

 if stat_type == "playtime":
 profile.playtime_hours = value
 message = f"■ Playtime set to **{value} hours**!"
 elif stat_type == "killerwin":
 profile.killer_wins = value
 message = f"■ Killer wins set to **{value}**!"
 elif stat_type == "survivorwin":
 profile.survivor_wins = value
 message = f"■ Survivor wins set to **{value}**!"
 else:
 await interaction.response.send_message("■ Invalid stat type!", ephemeral=True)
 return

 profile.last_updated = datetime.now()
 profile_system.save_profiles()

 await interaction.response.send_message(message, ephemeral=False)
