"""
TEAM MATCHMAKING SYSTEM - PART 13 (FIXED V2)
5v5 Tournament Results & Command Setup
Handles match results with SCORE TRACKING, and slash command registration
"""

import discord
from discord import app_commands
from typing import Optional
from team_matchmaking_part10 import TOURNAMENT_WIN_POINTS, TOURNAMENT_LOSS_POINTS


class Tournament5v5Results:
    """Handle 5v5 tournament match results"""
    
    @staticmethod
    async def handle_tournament_result(interaction: discord.Interaction, tournament_system, 
                                      multi_mode_stats, team_score: int):
        """Handle tournament round result reporting with scores (HOSTS ONLY)"""
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
        
        # Must be a team HOST
        user_team = match.is_team_host(user)
        if not user_team:
            await interaction.response.send_message("❌ Only team hosts can report results!", ephemeral=True)
            return
        
        # Validate score (0-7 points)
        if team_score < 0 or team_score > 7:
            await interaction.response.send_message("❌ Score must be between 0 and 7!", ephemeral=True)
            return
        
        # Record claim with score
        if user_team == "A":
            if match.team_a_claimed is not None:
                await interaction.response.send_message("❌ Your team already reported!", ephemeral=True)
                return
            match.team_a_claimed = team_score
        else:
            if match.team_b_claimed is not None:
                await interaction.response.send_message("❌ Your team already reported!", ephemeral=True)
                return
            match.team_b_claimed = team_score
        
        # Check if both reported
        if match.team_a_claimed is not None and match.team_b_claimed is not None:
            # Validate - scores must add up to 7
            total = match.team_a_claimed + match.team_b_claimed
            
            if total != 7:
                await interaction.response.send_message(
                    f"⚠️ **Invalid scores!** Scores must add up to 7 points total.\n"
                    f"**{match.team_a_name}:** {match.team_a_claimed} points\n"
                    f"**{match.team_b_name}:** {match.team_b_claimed} points\n"
                    f"**Total:** {total} (should be 7)\n\n"
                    f"Resetting reports...",
                    ephemeral=False
                )
                match.team_a_claimed = None
                match.team_b_claimed = None
                return
            
            # Determine winner (whoever got more points)
            if match.team_a_claimed > match.team_b_claimed:
                match.team_a_score += 1
                winner = "A"
            elif match.team_b_claimed > match.team_a_claimed:
                match.team_b_score += 1
                winner = "B"
            else:
                # Tie - both get 0 wins (shouldn't happen with 5 total points, but just in case)
                winner = None
            
            # Save round scores to history
            match.save_round_history()
            match.rounds_completed += 1
            
            # Show round results
            embed = discord.Embed(
                title=f"📊 Round {match.rounds_completed} Complete!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name=f"🔵 {match.team_a_name}",
                value=f"**+{match.team_a_claimed} points**",
                inline=True
            )
            
            embed.add_field(
                name=f"🔴 {match.team_b_name}",
                value=f"**+{match.team_b_claimed} points**",
                inline=True
            )
            
            if winner:
                winner_name = match.get_team_name(winner)
                embed.add_field(
                    name="🏆 Round Winner",
                    value=f"**{winner_name}**",
                    inline=False
                )
            
            # Show cumulative scores
            embed.add_field(
                name="📈 Overall Score",
                value=f"**{match.team_a_name}:** {match.team_a_score} wins\n"
                      f"**{match.team_b_name}:** {match.team_b_score} wins",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
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
                
                await match.thread.send(
                    f"⏭️ **Starting Round {match.current_round}/10...**"
                )
                
                # Start next round
                await tournament_system.start_round(match)
        
        else:
            # Waiting for other host
            other_team = "B" if user_team == "A" else "A"
            other_host = match.get_team_host(other_team)
            team_name = match.get_team_name(user_team)
            
            await interaction.response.send_message(
                f"✅ **{team_name}** reported **{team_score} points**.\n"
                f"Waiting for {other_host.mention} to report their score...",
                ephemeral=False
            )
    
    @staticmethod
    async def finalize_tournament(interaction, tournament_system, multi_mode_stats, match):
        """Finalize tournament and award points with detailed breakdown"""
        # Determine winner
        if match.team_a_score > match.team_b_score:
            winning_team = match.team_a
            losing_team = match.team_b
            winner_name = match.team_a_name
            loser_name = match.team_b_name
        else:
            winning_team = match.team_b
            losing_team = match.team_a
            winner_name = match.team_b_name
            loser_name = match.team_a_name
        
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
        
        # Create detailed breakdown from history
        team_a_round_scores = []
        team_b_round_scores = []
        team_a_total_points = 0
        team_b_total_points = 0
        
        for round_data in match.history:
            round_num = round_data["round"]
            # Get scores from history (we need to store them)
            # For now, we'll reconstruct from winner
            if round_data.get("team_a_points") is not None:
                team_a_round_scores.append(f"R{round_num}: +{round_data['team_a_points']}")
                team_b_round_scores.append(f"R{round_num}: +{round_data['team_b_points']}")
                team_a_total_points += round_data['team_a_points']
                team_b_total_points += round_data['team_b_points']
        
        # Create final embed
        embed = discord.Embed(
            title="🏆 5v5 TOURNAMENT COMPLETE!",
            description=f"**{winner_name}** wins the tournament!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📊 Final Wins",
            value=f"```\n{match.team_a_name}: {match.team_a_score} wins\n{match.team_b_name}: {match.team_b_score} wins\n```",
            inline=False
        )
        
        # Show round-by-round breakdown if available
        if team_a_round_scores:
            embed.add_field(
                name=f"📈 {match.team_a_name} - Round Scores",
                value="\n".join(team_a_round_scores) + f"\n**Total: {team_a_total_points} points**",
                inline=True
            )
            
            embed.add_field(
                name=f"📈 {match.team_b_name} - Round Scores",
                value="\n".join(team_b_round_scores) + f"\n**Total: {team_b_total_points} points**",
                inline=True
            )
        
        # Performance ratings based on average points per round
        def get_rating(total_points: int, rounds_played: int) -> tuple[str, str]:
            """Get rating emoji and text based on average points per round
            Max: 7 points per round (70 total for 10 rounds)
            Ratings:
            <3 avg = Bad
            3-4.9 avg = OK
            5-5.9 avg = OK
            6-6.9 avg = Nice  
            7 avg = Nice
            """
            avg = total_points / rounds_played if rounds_played > 0 else 0
            
            if avg < 3:
                return "😞", "how did you fumble this bad bro"
            elif avg < 6:
                return "😐", "that was a good match."
            else:  # avg >= 6
                return "😛", "great job!!!!!!!!!"
        
        team_a_emoji, team_a_rating = get_rating(team_a_total_points, match.rounds_completed)
        team_b_emoji, team_b_rating = get_rating(team_b_total_points, match.rounds_completed)
        
        embed.add_field(
            name="⚡ Performance Rating",
            value=f"**{match.team_a_name}:** {team_a_emoji} {team_a_rating} ({team_a_total_points}/{match.rounds_completed * 7} points - avg {team_a_total_points/match.rounds_completed:.1f})\n"
                  f"**{match.team_b_name}:** {team_b_emoji} {team_b_rating} ({team_b_total_points}/{match.rounds_completed * 7} points - avg {team_b_total_points/match.rounds_completed:.1f})",
            inline=False
        )
        
        embed.add_field(
            name="💎 ELO Points Awarded",
            value=f"**{winner_name}:** +{TOURNAMENT_WIN_POINTS} points per player\n"
                  f"**{loser_name}:** {TOURNAMENT_LOSS_POINTS} points per player",
            inline=False
        )
        
        embed.add_field(
            name="📋 Match Summary",
            value=f"Rounds Played: {match.rounds_completed}/10",
            inline=False
        )
        
        # Show winning team
        winning_members = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(winning_team)])
        embed.add_field(
            name=f"🏆 {winner_name}",
            value=winning_members,
            inline=False
        )
        
        await match.thread.send(embed=embed)
        
        # Clean up
        del tournament_system.active_matches[match.thread.id]
        
        # Archive thread after 1 hour
        await match.thread.edit(auto_archive_duration=60)


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
    
    @tree.command(name="selectmap", description="[5v5] Select map for the round (attacking host only)")
    @app_commands.describe(map_name="Map to play on")
    async def select_map(interaction: discord.Interaction, map_name: str):
        await Tournament5v5GameLogic.handle_map_select(interaction, tournament_system, map_name)
    
    @select_map.autocomplete('map_name')
    async def map_autocomplete(interaction: discord.Interaction, current: str):
        return Tournament5v5GameLogic.get_map_autocomplete(current)
    
    @tree.command(name="selectkiller", description="[5v5] Select killer player and character (attacking host only)")
    @app_commands.describe(
        player_number="Which player will be killer (1-5)",
        killer="Killer character"
    )
    async def select_killer(interaction: discord.Interaction, player_number: int, killer: str):
        await Tournament5v5GameLogic.handle_killer_select(interaction, tournament_system, player_number, killer)
    
    @select_killer.autocomplete('killer')
    async def killer_autocomplete(interaction: discord.Interaction, current: str):
        return Tournament5v5GameLogic.get_killer_autocomplete(current)
    
    @tree.command(name="tournamentban", description="[5v5] Ban a survivor (defending host only)")
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
    
    @tree.command(name="skipban", description="[5v5] Skip remaining bans (defending host only)")
    async def skip_ban(interaction: discord.Interaction):
        await Tournament5v5GameLogic.handle_skip_ban(interaction, tournament_system)
    
    @tree.command(name="tournamentpick", description="[5v5] Pick your survivor (defending team players)")
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
    
    @tree.command(name="reportscore", description="[5v5] Report your team's score for this round (0-7 points, host only)")
    @app_commands.describe(score="How many points your team scored (0-7)")
    async def report_score(interaction: discord.Interaction, score: int):
        await Tournament5v5Results.handle_tournament_result(
            interaction, tournament_system, multi_mode_stats, score
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
        
        team_name = match.get_team_name(team)
        
        embed = discord.Embed(
            title="❌ 5v5 Tournament Cancelled",
            description=f"Tournament cancelled by {user.mention} ({team_name} Host)",
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
