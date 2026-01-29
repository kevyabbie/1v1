"""
TEAM MATCHMAKING SYSTEM - PART 12 (FIXED)
5v5 Tournament Game Commands
Map selection, killer selection, banning, and picking phases
ONLY HOSTS can select maps and bans. ALL PLAYERS can pick survivors.
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
        """Attacking team HOST selects map"""
        thread_id = interaction.channel_id
        
        if thread_id not in tournament_system.active_matches:
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "map_select":
            await interaction.response.send_message("❌ Not in map selection phase!", ephemeral=True)
            return
        
        # Must be attacking team HOST
        user_team = match.is_team_host(user)
        attacking_team = match.get_attacking_team()
        
        if user_team != attacking_team:
            await interaction.response.send_message(
                f"❌ Only {match.get_attacking_host().mention} (attacking host) can select map!",
                ephemeral=True
            )
            return
        
        # Validate map
        if map_name not in MAPS:
            await interaction.response.send_message(f"❌ Invalid map: {map_name}", ephemeral=True)
            return
        
        # Set map
        match.selected_map = map_name
        match.current_phase = "killer_select"
        
        # Announce map
        await interaction.response.send_message(
            f"🗺️ **Map selected:** {map_name}",
            ephemeral=False
        )
        
        # Show killer recommendations to attacking team ONLY
        recommendations = MAP_KILLER_RECOMMENDATIONS.get(map_name, [])
        if recommendations:
            rec_text = ", ".join(recommendations)
            attacking_members = match.get_team_members(attacking_team)
            mentions = " ".join([m.mention for m in attacking_members])
            
            await match.thread.send(
                f"💡 **[ATTACKING TEAM ONLY]** {mentions}\n**Recommended killers for {map_name}:** {rec_text}"
            )
        
        # Next phase
        await match.thread.send(
            f"⚔️ **Phase 2: Killer Selection**\n"
            f"{match.get_attacking_host().mention} use `/selectkiller <player_number> <killer>` "
            f"to choose which player will be killer and their character!"
        )
        
        await tournament_system.update_status_message(match)
    
    @staticmethod
    async def handle_killer_select(interaction: discord.Interaction, tournament_system, 
                                   player_number: int, killer: str):
        """Attacking team HOST selects which player will be killer and which killer character"""
        thread_id = interaction.channel_id
        
        if thread_id not in tournament_system.active_matches:
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "killer_select":
            await interaction.response.send_message("❌ Not in killer selection phase!", ephemeral=True)
            return
        
        # Must be attacking team HOST
        user_team = match.is_team_host(user)
        attacking_team = match.get_attacking_team()
        
        if user_team != attacking_team:
            await interaction.response.send_message("❌ Only attacking host can select killer!", ephemeral=True)
            return
        
        # Validate player number (1-5)
        if player_number < 1 or player_number > 5:
            await interaction.response.send_message("❌ Player number must be 1-5!", ephemeral=True)
            return
        
        # Validate killer
        if killer not in KILLERS:
            await interaction.response.send_message(f"❌ Invalid killer: {killer}", ephemeral=True)
            return
        
        # Set killer
        player_index = player_number - 1
        match.selected_killer_player_index = player_index
        match.selected_killer_character = killer
        match.current_phase = "ban"
        
        # Get player
        attacking_members = match.get_team_members(attacking_team)
        killer_player = attacking_members[player_index]
        
        # Announce
        await interaction.response.send_message(
            f"⚔️ **Killer selected:** Player {player_number} ({killer_player.mention}) will play as **{killer}**!",
            ephemeral=False
        )
        
        # Show ban recommendations to defending team ONLY
        defending_team = match.get_defending_team()
        ban_recs = KILLER_BAN_RECOMMENDATIONS.get(killer, {})
        
        if ban_recs.get("solo") or ban_recs.get("combo"):
            defending_members = match.get_team_members(defending_team)
            mentions = " ".join([m.mention for m in defending_members])
            
            solo_bans = ", ".join(ban_recs.get("solo", []))
            combo_bans = " OR ".join([f"{a} + {b}" for a, b in ban_recs.get("combo", [])])
            
            rec_text = f"💡 **[DEFENDING TEAM ONLY]** {mentions}\n"
            rec_text += f"**Ban Recommendations vs {killer}:**\n"
            if solo_bans:
                rec_text += f"• **Solo Bans:** {solo_bans}\n"
            if combo_bans:
                rec_text += f"• **Combo Bans:** {combo_bans}"
            
            await match.thread.send(rec_text)
        
        # Next phase
        await match.thread.send(
            f"🚫 **Phase 3: Ban Phase**\n"
            f"{match.get_defending_host().mention} use `/tournamentban <survivor>` to ban survivors! "
            f"(Max {MAX_SURVIVOR_BANS} bans)\n"
            f"Use `/skipban` to proceed without banning all {MAX_SURVIVOR_BANS} survivors."
        )
        
        await tournament_system.update_status_message(match)
    
    @staticmethod
    async def handle_tournament_ban(interaction: discord.Interaction, tournament_system, survivor: str):
        """Defending team HOST bans survivors"""
        thread_id = interaction.channel_id
        
        if thread_id not in tournament_system.active_matches:
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        # Must be defending team HOST
        defending_team = match.get_defending_team()
        user_team = match.is_team_host(user)
        
        if user_team != defending_team:
            await interaction.response.send_message("❌ Only defending host can ban!", ephemeral=True)
            return
        
        # Check ban limit
        if len(match.banned_survivors) >= MAX_SURVIVOR_BANS:
            await interaction.response.send_message(f"❌ Already banned {MAX_SURVIVOR_BANS} survivors!", ephemeral=True)
            return
        
        # Validate survivor
        if survivor not in SURVIVORS:
            await interaction.response.send_message(f"❌ Invalid survivor: {survivor}", ephemeral=True)
            return
        
        # Check if already banned
        if survivor in match.banned_survivors:
            await interaction.response.send_message(f"❌ {survivor} is already banned!", ephemeral=True)
            return
        
        # Add ban
        match.banned_survivors.append(survivor)
        
        # Announce
        defending_team_name = match.get_team_name(defending_team)
        await interaction.response.send_message(
            f"🚫 **{defending_team_name}** banned **{survivor}**! ({len(match.banned_survivors)}/{MAX_SURVIVOR_BANS})",
            ephemeral=False
        )
        
        # Check if bans complete
        if len(match.banned_survivors) >= MAX_SURVIVOR_BANS:
            match.current_phase = "pick"
            await match.thread.send(
                f"✅ **Phase 4: Pick Phase**\n"
                f"Defending team ({defending_team_name}), ALL PLAYERS use `/tournamentpick <survivor>` to pick your survivors!\n"
                f"Each of the 5 players must pick a unique survivor (that hasn't been banned)."
            )
        else:
            await match.thread.send(
                f"Ban {len(match.banned_survivors)}/{MAX_SURVIVOR_BANS} complete. "
                f"{match.get_defending_host().mention} can ban {MAX_SURVIVOR_BANS - len(match.banned_survivors)} more or use `/skipban` to continue."
            )
        
        await tournament_system.update_status_message(match)
    
    @staticmethod
    async def handle_skip_ban(interaction: discord.Interaction, tournament_system):
        """Defending team HOST skips remaining bans"""
        thread_id = interaction.channel_id
        
        if thread_id not in tournament_system.active_matches:
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "ban":
            await interaction.response.send_message("❌ Not in ban phase!", ephemeral=True)
            return
        
        # Must be defending team HOST
        defending_team = match.get_defending_team()
        user_team = match.is_team_host(user)
        
        if user_team != defending_team:
            await interaction.response.send_message("❌ Only defending host can skip bans!", ephemeral=True)
            return
        
        # Move to pick phase
        match.current_phase = "pick"
        defending_team_name = match.get_team_name(defending_team)
        
        await interaction.response.send_message(
            f"⏭️ **Bans skipped** ({len(match.banned_survivors)}/{MAX_SURVIVOR_BANS} used)\n"
            f"✅ **Phase 4: Pick Phase**\n"
            f"Defending team ({defending_team_name}), ALL PLAYERS use `/tournamentpick <survivor>` to pick your survivors!\n"
            f"Each of the 5 players must pick a unique survivor.",
            ephemeral=False
        )
        
        await tournament_system.update_status_message(match)
    
    @staticmethod
    async def handle_tournament_pick(interaction: discord.Interaction, tournament_system, survivor: str):
        """Defending team PLAYERS (all 5) pick their survivors"""
        thread_id = interaction.channel_id
        
        if thread_id not in tournament_system.active_matches:
            await interaction.response.send_message("❌ No active 5v5 match!", ephemeral=True)
            return
        
        match = tournament_system.active_matches[thread_id]
        user = interaction.user
        
        # Check phase
        if match.current_phase != "pick":
            await interaction.response.send_message("❌ Not in pick phase!", ephemeral=True)
            return
        
        # Must be on defending team
        defending_team = match.get_defending_team()
        user_team = match.get_user_team(user)
        
        if user_team != defending_team:
            await interaction.response.send_message("❌ Only defending team can pick!", ephemeral=True)
            return
        
        # Get player index
        user_index = match.get_user_index_in_team(user)
        
        if user_index is None:
            await interaction.response.send_message("❌ Could not find your position!", ephemeral=True)
            return
        
        # Check if already picked
        if user_index in match.round_survivor_picks:
            await interaction.response.send_message(
                f"❌ You already picked {match.round_survivor_picks[user_index]}!",
                ephemeral=True
            )
            return
        
        # Validate survivor
        if survivor not in SURVIVORS:
            await interaction.response.send_message(f"❌ Invalid survivor: {survivor}", ephemeral=True)
            return
        
        # Check if banned
        if survivor in match.banned_survivors:
            await interaction.response.send_message(f"❌ {survivor} is banned!", ephemeral=True)
            return
        
        # Check if already picked by team
        if survivor in match.round_survivor_picks.values():
            await interaction.response.send_message(f"❌ {survivor} already picked by teammate!", ephemeral=True)
            return
        
        # Add pick
        match.round_survivor_picks[user_index] = survivor
        
        # Announce
        defending_team_name = match.get_team_name(defending_team)
        await interaction.response.send_message(
            f"✅ **{defending_team_name}** Player {user_index + 1} ({user.mention}) picked **{survivor}**! "
            f"({len(match.round_survivor_picks)}/5)",
            ephemeral=False
        )
        
        # Check if all picks complete
        if match.is_picks_complete():
            match.current_phase = "results"
            
            # Create summary embed
            embed = discord.Embed(
                title=f"🎮 ROUND {match.current_round} READY!",
                description="All selections complete! Play the round now.",
                color=discord.Color.green()
            )
            
            embed.add_field(name="🗺️ Map", value=match.selected_map, inline=True)
            
            attacking_members = match.get_team_members(match.get_attacking_team())
            killer_player = attacking_members[match.selected_killer_player_index]
            embed.add_field(
                name="⚔️ Killer",
                value=f"Player {match.selected_killer_player_index + 1}: {killer_player.mention}\n**{match.selected_killer_character}**",
                inline=True
            )
            
            if match.banned_survivors:
                embed.add_field(
                    name="🚫 Bans",
                    value=", ".join(match.banned_survivors),
                    inline=False
                )
            
            defending_members = match.get_team_members(defending_team)
            survivors_text = []
            for i in range(5):
                player = defending_members[i]
                survivor = match.round_survivor_picks[i]
                survivors_text.append(f"Player {i+1} ({player.mention}): **{survivor}**")
            
            embed.add_field(
                name="🛡️ Survivors",
                value="\n".join(survivors_text),
                inline=False
            )
            
            embed.set_footer(text="After playing, hosts use /tournamentwon or /tournamentloss to report results!")
            
            await match.thread.send(embed=embed)
        
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
