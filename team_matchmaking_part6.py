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
            await interaction.response.send_message("❌ No active team match!", ephemeral=True)
            return
        
        match = team_mm_system.active_matches[thread_id]
        user = interaction.user
        
        # Check if ban phase
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        # Check if user is a team host
        team = match.is_team_host(user)
        if not team:
            await interaction.response.send_message("❌ Only team hosts can ban!", ephemeral=True)
            return
        
        # Check if team can still ban
        if not match.can_ban(team):
            await interaction.response.send_message(
                f"❌ Your team has already banned {match.get_ban_limit()} character(s)!",
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
            await interaction.response.send_message(f"❌ Invalid character: {character}", ephemeral=True)
            return
        
        # Check if already banned
        if matched_char in match.team_a_bans or matched_char in match.team_b_bans:
            await interaction.response.send_message(f"❌ {matched_char} is already banned!", ephemeral=True)
            return
        
        # Add ban
        match.add_ban(team, matched_char)
        
        # Announce
        team_name = "Team A 🔵" if team == "A" else "Team B 🔴"
        await interaction.response.send_message(
            f"🚫 **{team_name}** banned **{matched_char}**!",
            ephemeral=False
        )
        
        # Check if ban phase is complete
        ban_limit = match.get_ban_limit()
        if len(match.team_a_bans) >= ban_limit and len(match.team_b_bans) >= ban_limit:
            match.current_phase = "pick"
            await match.thread.send("🎯 **BAN PHASE COMPLETE!** Starting **PICK PHASE - Round 1**...")
        
        await team_mm_system.update_match_status(match)
    
    @staticmethod
    async def handle_team_pick(interaction: discord.Interaction, team_mm_system, character: str):
        """Handle team pick command"""
        thread_id = interaction.channel_id
        
        if thread_id not in team_mm_system.active_matches:
            await interaction.response.send_message("❌ No active team match!", ephemeral=True)
            return
        
        match = team_mm_system.active_matches[thread_id]
        user = interaction.user
        
        # Check if pick phase
        if match.current_phase != "pick":
            await interaction.response.send_message("❌ Not in pick phase!", ephemeral=True)
            return
        
        # Get user's team
        team = match.get_user_team(user)
        if not team:
            await interaction.response.send_message("❌ You're not in this match!", ephemeral=True)
            return
        
        # Get user's index in team
        team_members = match.get_team_members(team)
        user_index = None
        for i, member in enumerate(team_members):
            if member.id == user.id:
                user_index = i
                break
        
        if user_index is None:
            await interaction.response.send_message("❌ Could not find your position!", ephemeral=True)
            return
        
        # Get round pattern
        pattern = match.get_round_pattern(match.current_round)
        team_pattern = pattern[f"team_{team.lower()}"]
        
        if user_index >= len(team_pattern):
            await interaction.response.send_message("❌ You don't have a role this round!", ephemeral=True)
            return
        
        required_role = team_pattern[user_index]
        
        # Check if already picked
        picks = match.team_a_picks if team == "A" else match.team_b_picks
        if user_index in picks:
            await interaction.response.send_message(
                f"❌ You've already picked {picks[user_index]}!",
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
                f"❌ You must pick a **{required_role}**! {character} is not valid.",
                ephemeral=True
            )
            return
        
        # Check if banned
        if matched_char in match.team_a_bans or matched_char in match.team_b_bans:
            await interaction.response.send_message(f"❌ {matched_char} is banned!", ephemeral=True)
            return
        
        # Check if already picked by team (survivors only)
        if required_role == "survivor":
            if matched_char in picks.values():
                await interaction.response.send_message(
                    f"❌ {matched_char} is already picked by your team!",
                    ephemeral=True
                )
                return
        
        # Add pick
        match.add_pick(team, user_index, matched_char)
        
        # Announce
        team_name = "Team A 🔵" if team == "A" else "Team B 🔴"
        await interaction.response.send_message(
            f"✅ **{team_name}** {user.mention} picked **{matched_char}** ({required_role.capitalize()})!",
            ephemeral=False
        )
        
        # Check if round is complete
        if match.is_pick_phase_complete():
            match.current_phase = "results"
            await match.thread.send(
                f"🎉 **ROUND {match.current_round} PICKS COMPLETE!**\n"
                f"**Current Score:** {match.team_a_score}-{match.team_b_score}\n"
                f"Play the round and hosts use `/teamwon` or `/teamloss` to report!"
            )
        
        await team_mm_system.update_match_status(match)
    
    @staticmethod
    async def handle_team_result(interaction: discord.Interaction, team_mm_system, result: str):
        """Handle team match result reporting"""
        thread_id = interaction.channel_id
        
        if thread_id not in team_mm_system.active_matches:
            await interaction.response.send_message("❌ No active team match!", ephemeral=True)
            return
        
        match = team_mm_system.active_matches[thread_id]
        user = interaction.user
        
        # Check if results phase
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Complete the pick phase first!", ephemeral=True)
            return
        
        # Check if user is a team host
        team = match.is_team_host(user)
        if not team:
            await interaction.response.send_message("❌ Only team hosts can report results!", ephemeral=True)
            return
        
        # Record claim
        if team == "A":
            if match.team_a_claimed:
                await interaction.response.send_message("❌ Your team already reported!", ephemeral=True)
                return
            match.team_a_claimed = result
        else:
            if match.team_b_claimed:
                await interaction.response.send_message("❌ Your team already reported!", ephemeral=True)
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
                    "⚠ **Results don't match!** Please verify who won.",
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
                match.current_round = match.total_rounds  # Repeat last round
                match.reset_picks_for_next_round()
                
                await interaction.response.send_message(
                    f"⚖️ **TIEBREAKER!** Score is tied {match.team_a_score}-{match.team_b_score}\n"
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
                    f"✅ **Round {match.rounds_completed} Complete!**\n"
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
                f"✅ Team {team} reported a **{result}**.\n"
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
            winner_name = "Team A 🔵"
            loser_name = "Team B 🔴"
        else:
            winning_team = match.team_b
            losing_team = match.team_a
            winner_name = "Team B 🔴"
            loser_name = "Team A 🔵"
        
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
            stats.points = max(0, stats.points + loss_points)  # Prevent negative
            stats.losses += 1
        
        team_mm_system.multi_mode_stats.save_stats()
        
        embed = discord.Embed(
            title=f"🏆 {match.mode.upper()} Match Complete!",
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
