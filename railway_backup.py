#!/usr/bin/env python3
"""
RAILWAY-COMPATIBLE BACKUP SYSTEM WITH USER NOTIFICATIONS
- Automatically backs up on restart (when you push to GitHub)
- Sends notification to all users in the channel
- Works with ephemeral storage
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


# Helper function for auto-backup on startup with user notifications
async def railway_auto_backup_on_startup(client, backup_channel_id: int, notification_channel_id: Optional[int] = None):
    """
    Create automatic backup when bot starts and notify users
    
    Args:
        client: Discord client
        backup_channel_id: Channel ID where backups will be posted
        notification_channel_id: Channel ID where to send notification (optional, defaults to backup channel)
    """
    try:
        backup_channel = client.get_channel(backup_channel_id)
        if not backup_channel:
            print(f"⚠️ Backup channel {backup_channel_id} not found!")
            return
        
        # Create backup
        backup_system = RailwayBackupSystem(backup_channel_id)
        backup_success = await backup_system.create_backup(backup_channel, manual=False)
        
        if not backup_success:
            return
        
        # Send notification to users
        notification_channel = backup_channel
        if notification_channel_id:
            notification_channel = client.get_channel(notification_channel_id)
            if not notification_channel:
                notification_channel = backup_channel
        
        # Get all users who have data
        all_users = set()
        
        # Get users from stats
        if os.path.exists(backup_system.stats_file):
            with open(backup_system.stats_file, 'r') as f:
                stats_data = json.load(f)
                for mode, players in stats_data.items():
                    for user_id in players.keys():
                        all_users.add(int(user_id))
        
        # Get users from profiles
        if os.path.exists(backup_system.profiles_file):
            with open(backup_system.profiles_file, 'r') as f:
                profiles_data = json.load(f)
                for user_id in profiles_data.keys():
                    all_users.add(int(user_id))
        
        # Create notification embed
        embed = discord.Embed(
            title="🔄 Bot Restarted & Data Backed Up!",
            description="The bot has been restarted and your data has been automatically backed up.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="✅ What Happened",
            value=(
                "• Bot restarted (new update deployed)\n"
                "• All player data backed up automatically\n"
                "• Your stats, profiles, and banners are safe!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Backup Info",
            value=f"• **Players backed up:** {len(all_users)}\n"
                  f"• **Backup location:** <#{backup_channel_id}>\n"
                  f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Everything Still Works",
            value="All your progress is saved! Continue playing normally.",
            inline=False
        )
        
        embed.set_footer(text="Your data is automatically backed up on every restart")
        
        # Create mentions string (limit to avoid spam)
        if len(all_users) <= 50:
            # Mention all users if 50 or fewer
            mentions = " ".join([f"<@{uid}>" for uid in list(all_users)[:50]])
            await notification_channel.send(
                content=f"📢 Attention all players: {mentions}",
                embed=embed
            )
        else:
            # Just send embed without mentions if too many users
            await notification_channel.send(
                content=f"📢 **{len(all_users)} players** - Your data has been backed up!",
                embed=embed
            )
        
        print(f"✅ Sent restart notification to {len(all_users)} user(s)")
    
    except Exception as e:
        print(f"❌ Auto-backup or notification failed: {e}")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║       RAILWAY BACKUP SYSTEM WITH USER NOTIFICATIONS              ║
╚═══════════════════════════════════════════════════════════════════╝

FEATURES:
  ✅ Auto-backup on bot startup (when you push to GitHub)
  ✅ Sends notification to ALL users in channel
  ✅ Uploads backups to Discord (survives Railway restarts)
  ✅ Manual backups via /backup command
  ✅ Restore via /restore command
  ✅ Single user backups via /backupuser command

WHAT HAPPENS ON RESTART:
  1. Bot detects restart (new GitHub commit deployed)
  2. Creates automatic backup of all data
  3. Uploads backup files to Discord channel
  4. Sends notification mentioning ALL users
  5. Users see: "Bot restarted & your data is backed up!"

SETUP:
  await railway_auto_backup_on_startup(
      client,
      backup_channel_id=1234567890,
      notification_channel_id=9876543210  # Where to notify users
  )

If notification_channel_id is not provided, notifications go to backup channel.
    """)
