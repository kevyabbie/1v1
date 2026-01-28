#!/usr/bin/env python3
"""
RAILWAY-COMPATIBLE BACKUP SYSTEM
Works with ephemeral storage - uploads backups to Discord channel
Perfect for Railway deployments where local storage is temporary
"""

import json
import os
import discord
from discord import File
from datetime import datetime
from io import BytesIO
from typing import Optional, Dict
import asyncio


class RailwayBackupSystem:
    """Backup system that stores backups in a Discord channel"""
    
    def __init__(self, backup_channel_id: int):
        """
        Initialize backup system
        
        Args:
            backup_channel_id: Discord channel ID where backups will be posted
        """
        self.backup_channel_id = backup_channel_id
        self.stats_file = "multi_mode_stats.json"
        self.profiles_file = "player_profiles.json"
        self.legacy_stats_file = "player_stats.json"
    
    async def create_backup(self, channel: discord.TextChannel, manual: bool = False) -> bool:
        """
        Create backup and upload to Discord channel
        
        Args:
            channel: Discord channel to upload backup to
            manual: If True, marks as manual backup
        
        Returns:
            True if successful
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_type = "manual" if manual else "auto"
        
        files_to_upload = []
        backup_summary = []
        
        try:
            # Backup multi-mode stats
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats_data = json.load(f)
                
                # Count players
                total_players = sum(len(players) for players in stats_data.values())
                
                # Create file in memory
                stats_json = json.dumps(stats_data, indent=2)
                stats_file = File(
                    BytesIO(stats_json.encode('utf-8')),
                    filename=f"multi_mode_stats_{backup_type}_{timestamp}.json"
                )
                files_to_upload.append(stats_file)
                backup_summary.append(f"📊 Leaderboard ({total_players} players)")
            
            # Backup player profiles
            if os.path.exists(self.profiles_file):
                with open(self.profiles_file, 'r') as f:
                    profiles_data = json.load(f)
                
                profiles_json = json.dumps(profiles_data, indent=2)
                profiles_file = File(
                    BytesIO(profiles_json.encode('utf-8')),
                    filename=f"player_profiles_{backup_type}_{timestamp}.json"
                )
                files_to_upload.append(profiles_file)
                backup_summary.append(f"👤 Profiles ({len(profiles_data)} players)")
            
            # Backup legacy stats
            if os.path.exists(self.legacy_stats_file):
                with open(self.legacy_stats_file, 'r') as f:
                    legacy_data = json.load(f)
                
                legacy_json = json.dumps(legacy_data, indent=2)
                legacy_file = File(
                    BytesIO(legacy_json.encode('utf-8')),
                    filename=f"player_stats_legacy_{backup_type}_{timestamp}.json"
                )
                files_to_upload.append(legacy_file)
                backup_summary.append(f"🎮 Legacy Stats ({len(legacy_data)} players)")
            
            if not files_to_upload:
                await channel.send("⚠️ No player data files found to backup!")
                return False
            
            # Create embed
            embed = discord.Embed(
                title=f"{'🔒 MANUAL' if manual else '🤖 AUTO'} BACKUP",
                description=f"Backup created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.gold() if manual else discord.Color.blue()
            )
            
            embed.add_field(
                name="📦 Files Backed Up",
                value="\n".join(backup_summary),
                inline=False
            )
            
            embed.add_field(
                name="⏰ Timestamp",
                value=f"`{timestamp}`",
                inline=False
            )
            
            if manual:
                embed.add_field(
                    name="🔒 Manual Backup",
                    value="This backup will be preserved. Download files to restore later.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🤖 Automatic Backup",
                    value="Created on bot startup. Download files to restore if needed.",
                    inline=False
                )
            
            embed.set_footer(text="Download these files to restore data later")
            
            # Upload to Discord
            await channel.send(
                embed=embed,
                files=files_to_upload
            )
            
            print(f"✅ Backup uploaded to Discord channel (ID: {channel.id})")
            return True
        
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            await channel.send(f"❌ Backup failed: {str(e)}")
            return False
    
    async def restore_from_message(self, message: discord.Message, overwrite: bool = True) -> bool:
        """
        Restore backup from Discord message attachments
        
        Args:
            message: Discord message containing backup files
            overwrite: If True, overwrites existing data
        
        Returns:
            True if successful
        """
        if not message.attachments:
            print("❌ Message has no attachments")
            return False
        
        restored_files = []
        
        try:
            for attachment in message.attachments:
                filename = attachment.filename
                
                # Download file
                file_data = await attachment.read()
                
                # Determine which file it is
                if "multi_mode_stats" in filename:
                    target_file = self.stats_file
                    file_type = "Leaderboard Stats"
                elif "player_profiles" in filename:
                    target_file = self.profiles_file
                    file_type = "Player Profiles"
                elif "player_stats_legacy" in filename:
                    target_file = self.legacy_stats_file
                    file_type = "Legacy Stats"
                else:
                    print(f"⏭️ Skipping unknown file: {filename}")
                    continue
                
                # Parse JSON
                data = json.loads(file_data.decode('utf-8'))
                
                # Save to file
                with open(target_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                restored_files.append(file_type)
                print(f"✅ Restored {file_type} from {filename}")
            
            if restored_files:
                print(f"\n✅ Successfully restored: {', '.join(restored_files)}")
                return True
            else:
                print("❌ No valid backup files found in message")
                return False
        
        except Exception as e:
            print(f"❌ Error restoring backup: {e}")
            return False
    
    async def backup_single_user(self, channel: discord.TextChannel, user_id: int) -> bool:
        """
        Backup data for a specific user
        
        Args:
            channel: Discord channel to upload to
            user_id: User ID to backup
        
        Returns:
            True if successful
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id_str = str(user_id)
        
        backup_data = {
            "user_id": user_id,
            "backup_timestamp": timestamp,
            "backup_datetime": datetime.now().isoformat(),
            "stats": {},
            "profile": None
        }
        
        data_found = False
        
        # Get stats
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r') as f:
                all_stats = json.load(f)
            
            for mode, players in all_stats.items():
                if user_id_str in players:
                    backup_data["stats"][mode] = players[user_id_str]
                    data_found = True
        
        # Get profile
        if os.path.exists(self.profiles_file):
            with open(self.profiles_file, 'r') as f:
                all_profiles = json.load(f)
            
            if user_id_str in all_profiles:
                backup_data["profile"] = all_profiles[user_id_str]
                data_found = True
        
        if not data_found:
            await channel.send(f"❌ No data found for user {user_id}")
            return False
        
        # Create embed
        embed = discord.Embed(
            title=f"👤 USER BACKUP - {user_id}",
            description=f"Backup created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=discord.Color.purple()
        )
        
        # Show what was backed up
        if backup_data["stats"]:
            modes = ", ".join(backup_data["stats"].keys())
            embed.add_field(name="📊 Stats", value=modes, inline=False)
        
        if backup_data["profile"]:
            profile = backup_data["profile"]
            profile_info = []
            if profile.get("banner_url"):
                profile_info.append("🎨 Banner")
            if profile.get("bio"):
                profile_info.append("📝 Bio")
            if profile.get("main_killer"):
                profile_info.append(f"⚔️ {profile['main_killer']}")
            if profile.get("main_survivor"):
                profile_info.append(f"🏃 {profile['main_survivor']}")
            
            if profile_info:
                embed.add_field(name="👤 Profile", value=" | ".join(profile_info), inline=False)
        
        embed.set_footer(text=f"Timestamp: {timestamp}")
        
        # Create file
        backup_json = json.dumps(backup_data, indent=2)
        backup_file = File(
            BytesIO(backup_json.encode('utf-8')),
            filename=f"user_{user_id}_backup_{timestamp}.json"
        )
        
        await channel.send(embed=embed, file=backup_file)
        
        print(f"✅ User backup uploaded for {user_id}")
        return True


def setup_railway_backup_commands(tree, client, backup_channel_id: int):
    """
    Setup Discord commands for Railway backup system
    
    Args:
        tree: Command tree
        client: Discord client
        backup_channel_id: Channel ID where backups are stored
    """
    backup_system = RailwayBackupSystem(backup_channel_id)
    
    @tree.command(name="backup", description="[ADMIN] Create manual backup (uploads to backup channel)")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def create_backup(interaction: discord.Interaction):
        """Create a manual backup"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get backup channel
            backup_channel = client.get_channel(backup_channel_id)
            if not backup_channel:
                await interaction.followup.send(
                    f"❌ Backup channel not found! (ID: {backup_channel_id})",
                    ephemeral=True
                )
                return
            
            # Create backup
            success = await backup_system.create_backup(backup_channel, manual=True)
            
            if success:
                await interaction.followup.send(
                    f"✅ Manual backup created and uploaded to <#{backup_channel_id}>!\n"
                    f"Download the files from that channel to restore later.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Backup failed. Check bot logs.",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @tree.command(name="restore", description="[ADMIN] Restore from backup (reply to backup message)")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def restore_backup(interaction: discord.Interaction):
        """Restore from backup message"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if this is a reply
            if not interaction.message or not interaction.message.reference:
                await interaction.followup.send(
                    "❌ Please use this command as a reply to a backup message!",
                    ephemeral=True
                )
                return
            
            # Get the message being replied to
            replied_message = await interaction.channel.fetch_message(
                interaction.message.reference.message_id
            )
            
            if not replied_message.attachments:
                await interaction.followup.send(
                    "❌ That message has no backup files!",
                    ephemeral=True
                )
                return
            
            # Restore from message
            await interaction.followup.send(
                "🔄 Restoring backup... This may take a moment.",
                ephemeral=True
            )
            
            success = await backup_system.restore_from_message(replied_message)
            
            if success:
                await interaction.followup.send(
                    "✅ Backup restored successfully!\n"
                    "⚠️ **Restart the bot** for changes to take full effect.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Restore failed. Check bot logs.",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @tree.command(name="backupuser", description="[ADMIN] Backup specific user's data")
    @discord.app_commands.describe(user_id="Discord user ID to backup")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def backup_user(interaction: discord.Interaction, user_id: str):
        """Backup specific user"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate user ID
            try:
                uid = int(user_id)
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid user ID! Must be a number.",
                    ephemeral=True
                )
                return
            
            # Get backup channel
            backup_channel = client.get_channel(backup_channel_id)
            if not backup_channel:
                await interaction.followup.send(
                    f"❌ Backup channel not found! (ID: {backup_channel_id})",
                    ephemeral=True
                )
                return
            
            # Create user backup
            success = await backup_system.backup_single_user(backup_channel, uid)
            
            if success:
                await interaction.followup.send(
                    f"✅ User backup created for {user_id} in <#{backup_channel_id}>!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ No data found for user {user_id}",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    return backup_system


# Helper function for auto-backup on startup
async def railway_auto_backup_on_startup(client, backup_channel_id: int):
    """
    Create automatic backup when bot starts (Railway-compatible)
    
    Args:
        client: Discord client
        backup_channel_id: Channel ID where backups will be posted
    """
    try:
        backup_channel = client.get_channel(backup_channel_id)
        if not backup_channel:
            print(f"⚠️ Backup channel {backup_channel_id} not found!")
            return
        
        backup_system = RailwayBackupSystem(backup_channel_id)
        await backup_system.create_backup(backup_channel, manual=False)
    
    except Exception as e:
        print(f"❌ Auto-backup failed: {e}")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║              RAILWAY-COMPATIBLE BACKUP SYSTEM                     ║
╚═══════════════════════════════════════════════════════════════════╝

This backup system is designed for Railway deployments where local
storage is ephemeral (deleted on restart).

HOW IT WORKS:
  1. Backups are uploaded to a Discord channel as file attachments
  2. Download the files from Discord to restore later
  3. No local storage needed - everything is in Discord!

SETUP:
  1. Create a private Discord channel for backups
  2. Get the channel ID (right-click channel > Copy ID)
  3. Use that channel ID when setting up the backup system

FEATURES:
  ✅ Auto-backup on bot startup (uploads to Discord)
  ✅ Manual backups via /backup command
  ✅ Restore via /restore command (reply to backup message)
  ✅ Single user backups via /backupuser command
  ✅ No local storage needed
  ✅ Perfect for Railway, Render, Heroku, etc.

INTEGRATION EXAMPLE:
  ```python
  from railway_backup import (
      setup_railway_backup_commands,
      railway_auto_backup_on_startup
  )
  
  # In your bot setup
  BACKUP_CHANNEL_ID = 1234567890  # Your backup channel ID
  
  # Setup commands
  setup_railway_backup_commands(tree, client, BACKUP_CHANNEL_ID)
  
  # In on_ready event
  await railway_auto_backup_on_startup(client, BACKUP_CHANNEL_ID)
  ```

COMMANDS (In Discord):
  /backup              - Create manual backup (admin only)
  /backupuser <id>     - Backup specific user (admin only)
  /restore             - Restore (reply to a backup message)

RESTORE PROCESS:
  1. Find the backup message in your backup channel
  2. Reply to it with: /restore
  3. Bot will download and restore the files
  4. Restart bot for changes to take effect
    """)
