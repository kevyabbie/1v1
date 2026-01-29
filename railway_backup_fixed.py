#!/usr/bin/env python3
"""
RAILWAY-COMPATIBLE BACKUP SYSTEM - FIXED RESTORE
Fixed: /restore now uses message_id parameter instead of reply detection
"""

import json
import os
import discord
from discord import File, app_commands
from datetime import datetime
from io import BytesIO
from typing import Optional, Dict
import asyncio


class RailwayBackupSystem:
    """Backup system that stores backups in a Discord channel"""
    
    def __init__(self, backup_channel_id: int):
        self.backup_channel_id = backup_channel_id
        self.stats_file = "multi_mode_stats.json"
        self.profiles_file = "player_profiles.json"
        self.legacy_stats_file = "player_stats.json"
    
    async def create_backup(self, channel: discord.TextChannel, manual: bool = False) -> bool:
        """Create backup and upload to Discord channel"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_type = "manual" if manual else "auto"
        
        files_to_upload = []
        backup_summary = []
        
        try:
            # Backup multi-mode stats
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats_data = json.load(f)
                
                total_players = sum(len(players) for players in stats_data.values())
                
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
            
            embed.add_field(name="📦 Files Backed Up", value="\n".join(backup_summary), inline=False)
            embed.add_field(name="⏰ Timestamp", value=f"`{timestamp}`", inline=False)
            
            if manual:
                embed.add_field(
                    name="🔒 How to Restore",
                    value="1. Right-click this message\n2. Copy ID\n3. Use `/restore message_id:<paste_id_here>`",
                    inline=False
                )
            
            embed.set_footer(text="To restore: Right-click message > Copy ID > /restore message_id:<id>")
            
            # Upload to Discord
            await channel.send(embed=embed, files=files_to_upload)
            
            print(f"✅ Backup uploaded to Discord channel (ID: {channel.id})")
            return True
        
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            await channel.send(f"❌ Backup failed: {str(e)}")
            return False
    
    async def restore_from_message(self, message: discord.Message, overwrite: bool = True) -> tuple[bool, str]:
        """Restore backup from Discord message attachments"""
        if not message.attachments:
            return False, "No attachments found"
        
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
                return True, ', '.join(restored_files)
            else:
                return False, "No valid backup files found"
        
        except Exception as e:
            print(f"❌ Error restoring backup: {e}")
            return False, str(e)


def setup_railway_backup_commands(tree, client, backup_channel_id: int):
    """Setup Discord commands for Railway backup system"""
    backup_system = RailwayBackupSystem(backup_channel_id)
    
    @tree.command(name="backup", description="[ADMIN] Create manual backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_backup(interaction: discord.Interaction):
        """Create a manual backup"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            backup_channel = client.get_channel(backup_channel_id)
            if not backup_channel:
                await interaction.followup.send(
                    f"❌ Backup channel not found! (ID: {backup_channel_id})",
                    ephemeral=True
                )
                return
            
            success = await backup_system.create_backup(backup_channel, manual=True)
            
            if success:
                await interaction.followup.send(
                    f"✅ Manual backup created in <#{backup_channel_id}>!\n\n"
                    f"**To restore later:**\n"
                    f"1. Right-click the backup message\n"
                    f"2. Copy ID\n"
                    f"3. Use `/restore message_id:<paste_id_here>`",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("❌ Backup failed. Check bot logs.", ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @tree.command(name="restore", description="[ADMIN] Restore from backup")
    @app_commands.describe(message_id="Message ID of the backup (right-click message > Copy ID)")
    @app_commands.checks.has_permissions(administrator=True)
    async def restore_backup(interaction: discord.Interaction, message_id: str):
        """Restore from backup message using message ID"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Convert message_id to int
            try:
                msg_id = int(message_id)
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid message ID!\n\n"
                    "**How to get message ID:**\n"
                    "1. Right-click the backup message\n"
                    "2. Select 'Copy ID'\n"
                    "3. Paste it in the command",
                    ephemeral=True
                )
                return
            
            # Fetch the message
            try:
                backup_message = await interaction.channel.fetch_message(msg_id)
            except discord.NotFound:
                await interaction.followup.send(
                    "❌ Message not found!\n"
                    "Make sure you're using this command in the same channel as the backup message.",
                    ephemeral=True
                )
                return
            except discord.Forbidden:
                await interaction.followup.send("❌ Cannot access that message!", ephemeral=True)
                return
            
            # Check if message has attachments
            if not backup_message.attachments:
                await interaction.followup.send(
                    "❌ That message has no backup files!\n"
                    f"**Attachments found:** {len(backup_message.attachments)}",
                    ephemeral=True
                )
                return
            
            # Restore from message
            await interaction.followup.send("🔄 Restoring backup... This may take a moment.", ephemeral=True)
            
            success, details = await backup_system.restore_from_message(backup_message)
            
            if success:
                await interaction.followup.send(
                    f"✅ Backup restored successfully!\n\n"
                    f"**Restored files:** {details}\n\n"
                    f"⚠️ **Please restart the bot** for changes to take full effect.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Restore failed!\n\n"
                    f"**Error:** {details}\n\n"
                    f"**Files in message:** {', '.join([a.filename for a in backup_message.attachments])}",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    return backup_system


# Helper function for auto-backup on startup
async def railway_auto_backup_on_startup(client, backup_channel_id: int, notification_channel_id: Optional[int] = None):
    """Create automatic backup when bot starts"""
    try:
        backup_channel = client.get_channel(backup_channel_id)
        if not backup_channel:
            print(f"⚠️ Backup channel {backup_channel_id} not found!")
            return
        
        backup_system = RailwayBackupSystem(backup_channel_id)
        backup_success = await backup_system.create_backup(backup_channel, manual=False)
        
        if backup_success:
            print("✅ Automatic backup created on startup")
    
    except Exception as e:
        print(f"❌ Auto-backup failed: {e}")
