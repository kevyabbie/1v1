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
    create_leaderboard_embed,
    create_visual_leaderboard_embed
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
from team_matchmaking_1v1 import Matchmaking1v1System, setup_1v1_commands

# Optional import for ghost player commands (DEBUG feature)
try:
    from ghost_player_commands import GhostPlayerSystem, setup_ghost_player_commands
    GHOST_COMMANDS_AVAILABLE = True
except ImportError:
    GHOST_COMMANDS_AVAILABLE = False
    print("⚠️ Ghost player commands not available (ghost_player_commands.py not found)")


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
    team_mm_system.multi_mode_stats = multi_mode_stats  # Link stats system
    tournament_5v5_system = Tournament5v5System(party_system)
    tournament_5v5_system.multi_mode_stats = multi_mode_stats  # Link stats system
    
    # Initialize 1v1 matchmaking system
    matchmaking_1v1_system = Matchmaking1v1System(bot_client, multi_mode_stats)
    
    # Initialize ghost player system (DEBUG) - only if available
    ghost_system = None
    if GHOST_COMMANDS_AVAILABLE:
        ghost_system = GhostPlayerSystem(party_system)
    
    # ==================== PARTY COMMANDS ====================
    
    @tree.command(name="party", description="Create a new party")
    async def create_party(interaction: discord.Interaction):
        success, message = party_system.create_party(interaction.user)
        
        if success:
            party = party_system.get_user_party(interaction.user)
            embed = discord.Embed(
                title="👥 Party Created!",
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
    
    @tree.command(name="partyname", description="Change your party's name")
    @app_commands.describe(name="New party name (max 50 characters)")
    async def set_party_name(interaction: discord.Interaction, name: str):
        """Change the party name - anyone in party can use this"""
        success, message = party_system.set_party_name(interaction.user, name)
        
        if success:
            embed = discord.Embed(
                title="✅ Party Name Updated!",
                description=message,
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
    
    @tree.command(name="partyleave", description="Leave your current party")
    async def leave_party(interaction: discord.Interaction):
        success, message = party_system.leave_party(interaction.user)
        await interaction.response.send_message(message, ephemeral=True)
    
    @tree.command(name="partydisband", description="Disband your party (host only)")
    async def disband_party(interaction: discord.Interaction):
        success, message = party_system.leave_party(interaction.user)
        await interaction.response.send_message(message, ephemeral=True)
    
    @tree.command(name="partyinvite", description="Invite someone to your party")
    @app_commands.describe(user="User to invite")
    async def invite_party(interaction: discord.Interaction, user: discord.Member):
        success, message = party_system.invite_to_party(interaction.user, user)
        
        if success:
            await interaction.response.send_message(
                f"📨 {user.mention} You've been invited to {interaction.user.mention}'s party!\n"
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
                title="✅ Joined Party!",
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
                f"👢 {user.mention} has been kicked from the party."
            )
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    @tree.command(name="partymembers", description="View your party members")
    async def party_members(interaction: discord.Interaction):
        party = party_system.get_user_party(interaction.user)
        
        if not party:
            await interaction.response.send_message("❌ You're not in a party!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"👥 {party.party_name}",
            description=f"**Party Size:** {party.get_size()}/{party.max_size}",
            color=discord.Color.blue()
        )
        
        members_text = "\n".join([
            f"{i+1}. {m.mention}{' (Ketua)' if i == 0 else ''}"
            for i, m in enumerate(party.members)
        ])
        embed.add_field(name="Members", value=members_text, inline=False)
        
        if party.pending_invites:
            invites = [f"<@{uid}>" for uid in party.pending_invites.keys()]
            embed.add_field(name="Pending Invites", value="\n".join(invites), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    # ==================== TEAM MATCHMAKING COMMANDS ====================
    
    @tree.command(name="2v2", description="Queue for 2v2 match with your party")
    async def queue_2v2(interaction: discord.Interaction):
        await team_mm_system.queue_for_match(interaction, "2v2")
    
    @tree.command(name="3v3", description="Queue for 3v3 match with your party")
    async def queue_3v3(interaction: discord.Interaction):
        await team_mm_system.queue_for_match(interaction, "3v3")
    
    @tree.command(name="4v4", description="Queue for 4v4 match with your party")
    async def queue_4v4(interaction: discord.Interaction):
        await team_mm_system.queue_for_match(interaction, "4v4")
    
    @tree.command(name="cancelqueue", description="Cancel your matchmaking queue")
    async def cancel_queue(interaction: discord.Interaction):
        await team_mm_system.cancel_queue(interaction)
    
    @tree.command(name="teamcancel", description="Cancel team match (host only, no penalty)")
    async def team_cancel(interaction: discord.Interaction):
        thread_id = interaction.channel_id
        
        if thread_id not in team_mm_system.active_matches:
            await interaction.response.send_message("❌ No active team match in this thread!", ephemeral=True)
            return
        
        match = team_mm_system.active_matches[thread_id]
        user = interaction.user
        
        team = match.is_team_host(user)
        if not team:
            await interaction.response.send_message("❌ Only team hosts can cancel the match!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ Match Cancelled",
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
        
        if not leaderboard_data:
            await interaction.response.send_message(
                f"📊 No players have competed in {mode.upper()} yet!",
                ephemeral=True
            )
            return
        
        # Check if #1 player has a profile with banner
        top_player = leaderboard_data[0]
        top_profile = profile_system.profiles.get(top_player.user_id)
        
        # Create enhanced embed if top player has banner, otherwise simple
        if top_profile and top_profile.banner_url:
            embed = await create_visual_leaderboard_embed(
                mode, 
                leaderboard_data, 
                profile_system, 
                interaction.guild
            )
        else:
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
        return [app_commands.Choice(name=s, value=s) for k in filtered[:25]]
    
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
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        stats = multi_mode_stats.get_or_create_stats(user, mode)
        old_points = stats.points
        stats.points = max(0, points)
        multi_mode_stats.save_stats()
        
        await interaction.response.send_message(
            f"✅ Set {user.mention}'s {mode} points: {old_points} → {stats.points}",
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
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        stats = multi_mode_stats.get_or_create_stats(user, mode)
        stats.wins = max(0, wins)
        multi_mode_stats.save_stats()
        
        await interaction.response.send_message(
            f"✅ Set {user.mention}'s {mode} wins to {stats.wins}",
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
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        stats = multi_mode_stats.get_or_create_stats(user, mode)
        stats.losses = max(0, losses)
        multi_mode_stats.save_stats()
        
        await interaction.response.send_message(
            f"✅ Set {user.mention}'s {mode} losses to {stats.losses}",
            ephemeral=False
        )
    
    @tree.command(name="close", description="[ADMIN] Force close any active match thread")
    async def admin_close(interaction: discord.Interaction):
        """Admin command to force close any match thread without both players"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        thread_id = interaction.channel_id
        closed = False
        
        # Check in team matches (2v2, 3v3, 4v4)
        if thread_id in team_mm_system.active_matches:
            match = team_mm_system.active_matches[thread_id]
            del team_mm_system.active_matches[thread_id]
            
            embed = discord.Embed(
                title="🔒 Match Closed by Admin",
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
                title="🔒 Tournament Closed by Admin",
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
                "❌ No active match found in this thread!",
                ephemeral=True
            )
    
    # ==================== 5v5 TOURNAMENT COMMANDS ====================
    
    # Setup 5v5 tournament commands
    setup_5v5_tournament_commands(tree, tournament_5v5_system, multi_mode_stats)
    
    # ==================== 1v1 MATCHMAKING COMMANDS ====================
    
    # Setup 1v1 matchmaking commands
    setup_1v1_commands(tree, matchmaking_1v1_system)
    
    # ==================== GHOST PLAYER COMMANDS (DEBUG) ====================
    
    # Setup ghost player commands (only if module is available)
    if GHOST_COMMANDS_AVAILABLE:
        setup_ghost_player_commands(tree, ghost_system)
        print("✅ Ghost player commands loaded successfully")
    
    return {
        'party_system': party_system,
        'team_mm_system': team_mm_system,
        'tournament_5v5_system': tournament_5v5_system,
        'multi_mode_stats': multi_mode_stats,
        'profile_system': profile_system,
        'matchmaking_1v1_system': matchmaking_1v1_system,
        'ghost_system': ghost_system
    }
