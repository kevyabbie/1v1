"""
GHOST PLAYER COMMAND - DEBUG ONLY
Allows authorized users to add ghost players to their party for testing
Only accessible by user IDs: 822110342724190258, 1007678208713433158
"""

import discord
from discord import app_commands
from typing import Optional

# Authorized user IDs
AUTHORIZED_USER_IDS = [822110342724190258, 1007678208713433158]


class GhostPlayer:
    """A fake player object that mimics discord.Member"""
    def __init__(self, user_id: int, display_name: str, name: str):
        self.id = user_id
        self.display_name = display_name
        self.name = name
        self.mention = f"@{display_name}"
        self.avatar = None
        self.bot = False
    
    def __str__(self):
        return self.display_name
    
    def __repr__(self):
        return f"GhostPlayer({self.display_name})"


class GhostPlayerSystem:
    """Manages ghost players for debugging"""
    def __init__(self, party_system):
        self.party_system = party_system
        self.ghost_counter = 1
        self.ghosts_created = {}  # ghost_id -> GhostPlayer
    
    def create_ghost(self, host: discord.Member) -> tuple[bool, str, Optional[GhostPlayer]]:
        """Create a ghost player and add to host's party"""
        # Check authorization
        if host.id not in AUTHORIZED_USER_IDS:
            return False, "❌ You don't have permission to use this command!", None
        
        # Check if host has a party
        party = self.party_system.get_user_party(host)
        if not party:
            return False, "❌ You need to create a party first! Use `/party`", None
        
        # Check if user is host
        if not party.is_host(host):
            return False, "❌ Only the party host can add ghost players!", None
        
        # Check if party is full
        if party.get_size() >= party.max_size:
            return False, f"❌ Party is full! ({party.max_size}/{party.max_size})", None
        
        # Create ghost player
        ghost_name = f"Ghost_{self.ghost_counter}"
        # Use unique IDs starting from a high number to avoid conflicts
        ghost_id = 900000000000000000 + self.ghost_counter
        ghost = GhostPlayer(ghost_id, ghost_name, ghost_name)
        
        # Add to party
        if party.add_member(ghost):
            # Map ghost to party
            self.party_system.user_party_map[ghost_id] = host.id
            self.ghosts_created[ghost_id] = ghost
            self.ghost_counter += 1
            
            return True, f"✅ Added **{ghost_name}** to your party! ({party.get_size()}/{party.max_size})", ghost
        else:
            return False, "❌ Failed to add ghost player!", None
    
    def remove_ghost(self, host: discord.Member, ghost_number: int) -> tuple[bool, str]:
        """Remove a specific ghost player from party"""
        # Check authorization
        if host.id not in AUTHORIZED_USER_IDS:
            return False, "❌ You don't have permission to use this command!"
        
        # Check if host has a party
        party = self.party_system.get_user_party(host)
        if not party:
            return False, "❌ You don't have a party!"
        
        # Check if user is host
        if not party.is_host(host):
            return False, "❌ Only the party host can remove ghost players!"
        
        # Find the ghost
        ghost_name = f"Ghost_{ghost_number}"
        ghost_to_remove = None
        
        for member in party.members:
            if hasattr(member, 'display_name') and member.display_name == ghost_name:
                ghost_to_remove = member
                break
        
        if not ghost_to_remove:
            return False, f"❌ {ghost_name} not found in your party!"
        
        # Remove from party
        if party.remove_member(ghost_to_remove):
            # Remove from mapping
            if ghost_to_remove.id in self.party_system.user_party_map:
                del self.party_system.user_party_map[ghost_to_remove.id]
            if ghost_to_remove.id in self.ghosts_created:
                del self.ghosts_created[ghost_to_remove.id]
            
            return True, f"✅ Removed **{ghost_name}** from your party!"
        else:
            return False, "❌ Failed to remove ghost player!"
    
    def clear_all_ghosts(self, host: discord.Member) -> tuple[bool, str]:
        """Remove all ghost players from party"""
        # Check authorization
        if host.id not in AUTHORIZED_USER_IDS:
            return False, "❌ You don't have permission to use this command!"
        
        # Check if host has a party
        party = self.party_system.get_user_party(host)
        if not party:
            return False, "❌ You don't have a party!"
        
        # Check if user is host
        if not party.is_host(host):
            return False, "❌ Only the party host can remove ghost players!"
        
        # Find all ghosts
        ghosts_to_remove = []
        for member in party.members:
            if hasattr(member, 'display_name') and member.display_name.startswith("Ghost_"):
                ghosts_to_remove.append(member)
        
        if not ghosts_to_remove:
            return False, "❌ No ghost players in your party!"
        
        # Remove all ghosts
        removed_count = 0
        for ghost in ghosts_to_remove:
            if party.remove_member(ghost):
                if ghost.id in self.party_system.user_party_map:
                    del self.party_system.user_party_map[ghost.id]
                if ghost.id in self.ghosts_created:
                    del self.ghosts_created[ghost.id]
                removed_count += 1
        
        return True, f"✅ Removed {removed_count} ghost player(s) from your party!"


def setup_ghost_player_commands(tree: app_commands.CommandTree, ghost_system: GhostPlayerSystem):
    """Setup ghost player commands"""
    
    @tree.command(name="ghostadd", description="[DEBUG] Add a ghost player to your party")
    async def ghost_add(interaction: discord.Interaction):
        """Add a ghost player to party (authorized users only)"""
        success, message, ghost = ghost_system.create_ghost(interaction.user)
        
        if success:
            embed = discord.Embed(
                title="👻 Ghost Player Added",
                description=message,
                color=discord.Color.green()
            )
            
            party = ghost_system.party_system.get_user_party(interaction.user)
            if party:
                members_list = "\n".join([
                    f"{i+1}. {m.display_name}{' (Ketua)' if i == 0 else ''}"
                    for i, m in enumerate(party.members)
                ])
                embed.add_field(
                    name=f"Party Members ({party.get_size()}/{party.max_size})",
                    value=members_list,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    @tree.command(name="ghostremove", description="[DEBUG] Remove a ghost player from your party")
    @app_commands.describe(ghost_number="Ghost number to remove (e.g., 1 for Ghost_1)")
    async def ghost_remove(interaction: discord.Interaction, ghost_number: int):
        """Remove a specific ghost player (authorized users only)"""
        success, message = ghost_system.remove_ghost(interaction.user, ghost_number)
        
        if success:
            embed = discord.Embed(
                title="👻 Ghost Player Removed",
                description=message,
                color=discord.Color.orange()
            )
            
            party = ghost_system.party_system.get_user_party(interaction.user)
            if party:
                members_list = "\n".join([
                    f"{i+1}. {m.display_name}{' (Ketua)' if i == 0 else ''}"
                    for i, m in enumerate(party.members)
                ])
                embed.add_field(
                    name=f"Party Members ({party.get_size()}/{party.max_size})",
                    value=members_list,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    @tree.command(name="ghostclear", description="[DEBUG] Remove all ghost players from your party")
    async def ghost_clear(interaction: discord.Interaction):
        """Remove all ghost players (authorized users only)"""
        success, message = ghost_system.clear_all_ghosts(interaction.user)
        
        if success:
            embed = discord.Embed(
                title="👻 Ghosts Cleared",
                description=message,
                color=discord.Color.red()
            )
            
            party = ghost_system.party_system.get_user_party(interaction.user)
            if party:
                members_list = "\n".join([
                    f"{i+1}. {m.display_name}{' (Ketua)' if i == 0 else ''}"
                    for i, m in enumerate(party.members)
                ])
                embed.add_field(
                    name=f"Party Members ({party.get_size()}/{party.max_size})",
                    value=members_list,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    return ghost_system
