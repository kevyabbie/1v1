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
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "results":
            await interaction.response.send_message("❌ Complete the pick phase first!", ephemeral=True)
            return
        
        # Must be a team host
        user_team = match.is_team_host(user)
        if not user_team:
            await interaction.response.send_message("❌ Only team hosts can report results!", ephemeral=True)
            return
        
        # Record claim
        if user_team == "A":
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
                    "⚠ **Results don't match!** Please verify who won this round.",
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
                    f"✅ **Round {match.rounds_completed} Complete!**\n"
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
                f"✅ Team {user_team} reported a **{result}**.\n"
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
            winner_name = "Team A 🔵"
            loser_name = "Team B 🔴"
        else:
            winning_team = match.team_b
            losing_team = match.team_a
            winner_name = "Team B 🔴"
            loser_name = "Team A 🔵"
        
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
            title="🏆 5v5 TOURNAMENT COMPLETE!",
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
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Must be a team host
        team = match.is_team_host(user)
        if not team:
            await interaction.response.send_message("❌ Only team hosts can cancel!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ 5v5 Tournament Cancelled",
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
