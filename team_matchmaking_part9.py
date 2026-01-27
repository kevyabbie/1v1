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
        title=f"📋 {match.mode.upper()} Team Rosters",
        color=discord.Color.blue()
    )
    
    # Team A
    team_a_text = []
    for i, member in enumerate(match.team_a):
        role = "👑 Host" if member.id == match.team_a_host.id else f"Player {i+1}"
        team_a_text.append(f"{role}: {member.mention}")
    
    embed.add_field(
        name="🔵 Team A",
        value="\n".join(team_a_text),
        inline=True
    )
    
    # Team B
    team_b_text = []
    for i, member in enumerate(match.team_b):
        role = "👑 Host" if member.id == match.team_b_host.id else f"Player {i+1}"
        team_b_text.append(f"{role}: {member.mention}")
    
    embed.add_field(
        name="🔴 Team B",
        value="\n".join(team_b_text),
        inline=True
    )
    
    return embed


def create_round_summary_embed(match, round_num: int) -> discord.Embed:
    """Create embed showing what each player should pick for a round"""
    embed = discord.Embed(
        title=f"🎯 Round {round_num} - Pick Phase",
        description=f"**Current Score:** {match.team_a_score}-{match.team_b_score}",
        color=discord.Color.gold()
    )
    
    pattern = match.get_round_pattern(round_num)
    
    # Team A assignments
    team_a_assignments = []
    for i, role in enumerate(pattern["team_a"]):
        player = match.team_a[i]
        pick = match.team_a_picks.get(i, "❓ Not picked")
        emoji = "⚔️" if role == "killer" else "🏃"
        team_a_assignments.append(f"{emoji} {player.display_name}: {role.upper()} → {pick}")
    
    embed.add_field(
        name="🔵 Team A",
        value="\n".join(team_a_assignments),
        inline=False
    )
    
    # Team B assignments
    team_b_assignments = []
    for i, role in enumerate(pattern["team_b"]):
        player = match.team_b[i]
        pick = match.team_b_picks.get(i, "❓ Not picked")
        emoji = "⚔️" if role == "killer" else "🏃"
        team_b_assignments.append(f"{emoji} {player.display_name}: {role.upper()} → {pick}")
    
    embed.add_field(
        name="🔴 Team B",
        value="\n".join(team_b_assignments),
        inline=False
    )
    
    embed.set_footer(text="Use /teampick to select your character!")
    
    return embed


def format_team_name(team: str) -> str:
    """Format team letter into display name"""
    return "Team A 🔵" if team == "A" else "Team B 🔴"


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
    bar = "█" * progress + "░" * (10 - progress)
    
    return f"Progress: [{bar}] {completed}/{total} rounds"


def get_match_status_summary(match) -> str:
    """Get a one-line summary of match status"""
    if match.current_phase == "ban":
        return f"🚫 Ban Phase | Team A: {len(match.team_a_bans)}/{match.get_ban_limit()} | Team B: {len(match.team_b_bans)}/{match.get_ban_limit()}"
    elif match.current_phase == "pick":
        pattern = match.get_round_pattern(match.current_round)
        a_picks = len(match.team_a_picks)
        b_picks = len(match.team_b_picks)
        a_needed = len(pattern["team_a"])
        b_needed = len(pattern["team_b"])
        return f"🎯 Round {match.current_round} Pick Phase | Team A: {a_picks}/{a_needed} | Team B: {b_picks}/{b_needed}"
    elif match.current_phase == "results":
        a_claimed = "✅" if match.team_a_claimed else "⏳"
        b_claimed = "✅" if match.team_b_claimed else "⏳"
        return f"📊 Waiting for Results | Team A: {a_claimed} | Team B: {b_claimed}"
    else:
        return "❓ Unknown phase"


def create_tiebreaker_announcement_embed(match) -> discord.Embed:
    """Create dramatic tiebreaker announcement"""
    embed = discord.Embed(
        title="⚖️ TIEBREAKER ROUND!",
        description=f"The score is tied at **{match.team_a_score}-{match.team_b_score}**!\n\nThe final round will be played again to determine the winner!",
        color=discord.Color.orange()
    )
    
    embed.add_field(
        name="🔵 Team A",
        value="\n".join([m.mention for m in match.team_a]),
        inline=True
    )
    
    embed.add_field(
        name="🔴 Team B",
        value="\n".join([m.mention for m in match.team_b]),
        inline=True
    )
    
    embed.set_footer(text="Winner takes all! Good luck!")
    
    return embed


def create_waiting_for_queue_embed(mode: str, party) -> discord.Embed:
    """Create embed for party waiting in queue"""
    embed = discord.Embed(
        title=f"🔍 {mode.upper()} Matchmaking",
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
        value="⏳ Waiting for another team...",
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
