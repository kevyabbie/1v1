#!/usr/bin/env python3
"""
Railway Backup Script
Backs up all player data files to timestamped backups
Includes Discord bot integration for automated backups
"""

import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import discord
from discord import app_commands
from typing import Optional


def create_backup():
    """Create timestamped backups of all player data"""
    
    # Files to backup
    files_to_backup = [
        "multi_mode_stats.json",
        "player_profiles.json",
        "player_stats.json",  # Legacy file if it exists
    ]
    
    # Create backup directory if it doesn't exist
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Get timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("=" * 60)
    print(f"🔄 Creating Backup - {timestamp}")
    print("=" * 60)
    
    backed_up = 0
    skipped = 0
    backed_up_files = []
    
    for filename in files_to_backup:
        if os.path.exists(filename):
            # Create backup filename
            backup_filename = f"{backup_dir}/{filename.replace('.json', '')}_{timestamp}.json"
            
            try:
                # Copy file
                shutil.copy2(filename, backup_filename)
                
                # Get file size
                size = os.path.getsize(filename)
                size_kb = size / 1024
                
                print(f"✅ Backed up: {filename}")
                print(f"   → {backup_filename} ({size_kb:.2f} KB)")
                
                # Validate JSON
                with open(filename, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        print(f"   📊 Contains {len(data)} entries")
                
                backed_up += 1
                backed_up_files.append({
                    'original': filename,
                    'backup': backup_filename,
                    'size_kb': size_kb
                })
                
            except Exception as e:
                print(f"❌ Error backing up {filename}: {e}")
        else:
            print(f"⏭️  Skipped: {filename} (not found)")
            skipped += 1
    
    print("=" * 60)
    print(f"📦 Backup Summary:")
    print(f"   ✅ Backed up: {backed_up} file(s)")
    print(f"   ⏭️  Skipped: {skipped} file(s)")
    print(f"   📁 Location: {backup_dir.absolute()}")
    print("=" * 60)
    
    return backed_up > 0, backed_up_files, timestamp


def restore_from_backup(backup_file: str):
    """Restore from a specific backup file"""
    
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return False
    
    try:
        # Determine original filename
        backup_path = Path(backup_file)
        filename = backup_path.name
        
        # Remove timestamp to get original name
        # Format: multi_mode_stats_20240129_120000.json -> multi_mode_stats.json
        parts = filename.rsplit('_', 2)
        if len(parts) >= 3:
            original_name = f"{parts[0]}.json"
        else:
            print(f"❌ Invalid backup filename format: {filename}")
            return False
        
        print(f"🔄 Restoring {original_name} from {filename}...")
        
        # Create backup of current file if it exists
        if os.path.exists(original_name):
            current_backup = f"{original_name}.pre_restore_backup"
            shutil.copy2(original_name, current_backup)
            print(f"   💾 Current file backed up to: {current_backup}")
        
        # Restore
        shutil.copy2(backup_file, original_name)
        
        # Validate
        with open(original_name, 'r') as f:
            data = json.load(f)
            print(f"   ✅ Restored {len(data)} entries to {original_name}")
        
        print(f"✅ Restore complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error restoring: {e}")
        return False


def list_backups():
    """List all available backups"""
    
    backup_dir = Path("backups")
    
    if not backup_dir.exists():
        print("📁 No backups directory found")
        return []
    
    backups = sorted(backup_dir.glob("*.json"), reverse=True)
    
    if not backups:
        print("📁 No backups found")
        return []
    
    print("=" * 60)
    print("📦 Available Backups:")
    print("=" * 60)
    
    backup_list = []
    for backup in backups:
        size = backup.stat().st_size / 1024
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"📄 {backup.name}")
        print(f"   Size: {size:.2f} KB | Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        backup_list.append({
            'name': backup.name,
            'size_kb': size,
            'modified': modified
        })
    
    print("=" * 60)
    return backup_list


def show_stats_summary():
    """Show summary of current stats"""
    
    print("=" * 60)
    print("📊 Current Stats Summary:")
    print("=" * 60)
    
    summary = {}
    
    # Multi-mode stats
    if os.path.exists("multi_mode_stats.json"):
        try:
            with open("multi_mode_stats.json", 'r') as f:
                data = json.load(f)
                print("\n🎮 Multi-Mode Stats:")
                for mode, players in data.items():
                    print(f"   {mode}: {len(players)} players")
                    summary[f"mode_{mode}"] = len(players)
        except Exception as e:
            print(f"   ❌ Error reading multi_mode_stats.json: {e}")
    
    # Player profiles
    if os.path.exists("player_profiles.json"):
        try:
            with open("player_profiles.json", 'r') as f:
                data = json.load(f)
                print(f"\n👤 Player Profiles: {len(data)} profiles")
                summary['profiles'] = len(data)
        except Exception as e:
            print(f"   ❌ Error reading player_profiles.json: {e}")
    
    print("=" * 60)
    return summary


def clean_old_backups(keep_count: int = 10):
    """Keep only the most recent N backups"""
    
    backup_dir = Path("backups")
    
    if not backup_dir.exists():
        print("📁 No backups directory found")
        return 0
    
    # Group backups by base filename
    backup_groups = {}
    for backup in backup_dir.glob("*.json"):
        # Extract base name (e.g., "multi_mode_stats" from "multi_mode_stats_20240129_120000.json")
        parts = backup.name.rsplit('_', 2)
        if len(parts) >= 3:
            base_name = parts[0]
            if base_name not in backup_groups:
                backup_groups[base_name] = []
            backup_groups[base_name].append(backup)
    
    print(f"🧹 Cleaning old backups (keeping {keep_count} most recent per file)...")
    
    deleted = 0
    for base_name, backups in backup_groups.items():
        # Sort by modification time (newest first)
        sorted_backups = sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Delete old backups
        for old_backup in sorted_backups[keep_count:]:
            try:
                old_backup.unlink()
                print(f"   🗑️  Deleted: {old_backup.name}")
                deleted += 1
            except Exception as e:
                print(f"   ❌ Error deleting {old_backup.name}: {e}")
    
    if deleted == 0:
        print("   ✅ No old backups to delete")
    else:
        print(f"   ✅ Deleted {deleted} old backup(s)")
    
    return deleted


# ==================== DISCORD BOT INTEGRATION ====================

ADMIN_USER_ID = 822110342724190258


async def railway_auto_backup_on_startup(bot_client, backup_channel_id: int, notification_channel_id: int = 0):
    """
    Automatically create a backup when the bot starts
    This ensures there's always a recent backup available
    
    Args:
        bot_client: Discord bot client
        backup_channel_id: Channel ID for backup notifications
        notification_channel_id: Channel ID for user notifications (optional)
    """
    try:
        print("\n🔄 Creating automatic startup backup...")
        success, files, timestamp = create_backup()
        
        if success:
            print(f"✅ Startup backup created: {timestamp}")
            
            # Send notification to backup channel
            if backup_channel_id > 0:
                try:
                    backup_channel = bot_client.get_channel(backup_channel_id)
                    if backup_channel:
                        embed = discord.Embed(
                            title="🔄 Startup Backup Created",
                            description=f"Automatic backup created at bot startup\nTimestamp: `{timestamp}`",
                            color=discord.Color.blue()
                        )
                        
                        for file_info in files:
                            embed.add_field(
                                name=f"📄 {file_info['original']}",
                                value=f"Size: {file_info['size_kb']:.2f} KB",
                                inline=False
                            )
                        
                        embed.set_footer(text="Bot is now online and ready!")
                        await backup_channel.send(embed=embed)
                        print(f"✅ Backup notification sent to channel {backup_channel_id}")
                except Exception as e:
                    print(f"⚠️  Could not send backup notification: {e}")
            
            # Send user notification to notification channel if different
            if notification_channel_id > 0 and notification_channel_id != backup_channel_id:
                try:
                    notif_channel = bot_client.get_channel(notification_channel_id)
                    if notif_channel:
                        embed = discord.Embed(
                            title="🤖 Bot Online",
                            description="Matchmaking bot is now online and ready!",
                            color=discord.Color.green()
                        )
                        embed.add_field(
                            name="✅ Systems Ready",
                            value="• 1v1 Matchmaking\n• 2v2/3v3/4v4 Teams\n• 5v5 Tournaments\n• Profile System\n• Backup System",
                            inline=False
                        )
                        embed.set_footer(text=f"Startup backup created: {timestamp}")
                        await notif_channel.send(embed=embed)
                        print(f"✅ User notification sent to channel {notification_channel_id}")
                except Exception as e:
                    print(f"⚠️  Could not send user notification: {e}")
            
            return True
        else:
            print("⚠️  No files to backup on startup")
            return False
    except Exception as e:
        print(f"❌ Startup backup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def setup_railway_backup_commands(tree: app_commands.CommandTree, bot_client, backup_channel_id: int = 0):
    """Setup backup commands for Discord bot
    
    Args:
        tree: Discord command tree
        bot_client: Discord bot client
        backup_channel_id: Optional channel ID for backup notifications
    """
    
    @tree.command(name="backup", description="[ADMIN] Create a backup of all player data")
    async def backup_command(interaction: discord.Interaction):
        """Create backup of player data"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            success, files, timestamp = create_backup()
            
            if success:
                embed = discord.Embed(
                    title="💾 Backup Created Successfully",
                    description=f"Timestamp: `{timestamp}`",
                    color=discord.Color.green()
                )
                
                for file_info in files:
                    embed.add_field(
                        name=f"📄 {file_info['original']}",
                        value=f"Size: {file_info['size_kb']:.2f} KB",
                        inline=False
                    )
                
                embed.set_footer(text="Backups stored in /backups directory")
                await interaction.followup.send(embed=embed)
                
                # Send notification to backup channel if configured
                if backup_channel_id > 0:
                    try:
                        backup_channel = bot_client.get_channel(backup_channel_id)
                        if backup_channel:
                            await backup_channel.send(embed=embed)
                    except Exception as e:
                        print(f"⚠️  Could not send to backup channel: {e}")
            else:
                await interaction.followup.send("❌ No files to backup!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Backup failed: {e}", ephemeral=True)
    
    @tree.command(name="listbackups", description="[ADMIN] List all available backups")
    async def list_backups_command(interaction: discord.Interaction):
        """List all backups"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        backups = list_backups()
        
        if not backups:
            await interaction.response.send_message("📁 No backups found", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📦 Available Backups",
            color=discord.Color.blue()
        )
        
        # Show first 10 backups
        for backup in backups[:10]:
            embed.add_field(
                name=f"📄 {backup['name']}",
                value=f"Size: {backup['size_kb']:.2f} KB | {backup['modified'].strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
        
        if len(backups) > 10:
            embed.set_footer(text=f"Showing 10 of {len(backups)} backups")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @tree.command(name="restorebackup", description="[ADMIN] Restore data from a backup file")
    @app_commands.describe(backup_filename="Name of the backup file to restore from")
    async def restorebackup(interaction: discord.Interaction, backup_filename: str):
        """Restore from a backup"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Construct full path
            backup_path = f"backups/{backup_filename}"
            
            # Check if file exists
            if not os.path.exists(backup_path):
                await interaction.followup.send(
                    f"❌ Backup file not found: `{backup_filename}`\n"
                    f"Use `/listbackups` to see available backups.",
                    ephemeral=True
                )
                return
            
            # Confirm restoration
            embed = discord.Embed(
                title="⚠️ Confirm Restore",
                description=f"Are you sure you want to restore from `{backup_filename}`?",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="⚠️ Warning",
                value="This will **overwrite** current data!\nCurrent data will be backed up as `.pre_restore_backup`",
                inline=False
            )
            embed.set_footer(text="This action cannot be undone automatically")
            
            # For now, proceed with restore (in production, you'd want a confirmation button)
            success = restore_from_backup(backup_path)
            
            if success:
                result_embed = discord.Embed(
                    title="✅ Restore Complete",
                    description=f"Successfully restored from `{backup_filename}`",
                    color=discord.Color.green()
                )
                result_embed.add_field(
                    name="💾 Safety Backup",
                    value="Previous data saved with `.pre_restore_backup` extension",
                    inline=False
                )
                result_embed.set_footer(text="⚠️ Bot may need to restart to apply changes")
                
                await interaction.followup.send(embed=result_embed)
                
                # Send notification to backup channel if configured
                if backup_channel_id > 0:
                    try:
                        backup_channel = bot_client.get_channel(backup_channel_id)
                        if backup_channel:
                            await backup_channel.send(embed=result_embed)
                    except Exception as e:
                        print(f"⚠️  Could not send to backup channel: {e}")
            else:
                await interaction.followup.send("❌ Restore failed! Check logs for details.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Restore error: {e}", ephemeral=True)
    
    @restorebackup.autocomplete('backup_filename')
    async def restore_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for backup filenames"""
        backup_dir = Path("backups")
        
        if not backup_dir.exists():
            return []
        
        backups = sorted(backup_dir.glob("*.json"), reverse=True)
        
        # Filter by current input
        if current:
            backups = [b for b in backups if current.lower() in b.name.lower()]
        
        # Return up to 25 choices
        return [
            app_commands.Choice(name=backup.name, value=backup.name)
            for backup in backups[:25]
        ]
    
    @tree.command(name="statsummary", description="[ADMIN] Show current stats summary")
    async def stats_summary_command(interaction: discord.Interaction):
        """Show stats summary"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        summary = show_stats_summary()
        
        embed = discord.Embed(
            title="📊 Current Stats Summary",
            color=discord.Color.gold()
        )
        
        # Multi-mode stats
        modes = ["1v1", "2v2", "3v3", "4v4", "5v5"]
        mode_text = []
        for mode in modes:
            count = summary.get(f"mode_{mode}", 0)
            mode_text.append(f"**{mode}:** {count} players")
        
        if mode_text:
            embed.add_field(
                name="🎮 Multi-Mode Stats",
                value="\n".join(mode_text),
                inline=False
            )
        
        # Profiles
        if 'profiles' in summary:
            embed.add_field(
                name="👤 Player Profiles",
                value=f"{summary['profiles']} profiles",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @tree.command(name="cleanbackups", description="[ADMIN] Clean old backups (keep 10 most recent)")
    async def clean_backups_command(interaction: discord.Interaction):
        """Clean old backups"""
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=False)
        
        deleted = clean_old_backups(keep_count=10)
        
        embed = discord.Embed(
            title="🧹 Backup Cleanup Complete",
            description=f"Deleted {deleted} old backup(s)",
            color=discord.Color.orange()
        )
        
        embed.set_footer(text="Kept 10 most recent backups per file")
        
        await interaction.followup.send(embed=embed)
    
    print("✅ Railway backup commands loaded")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "backup" or command == "create":
            create_backup()
        
        elif command == "restore":
            if len(sys.argv) > 2:
                restore_from_backup(sys.argv[2])
            else:
                print("Usage: python railway_backup.py restore <backup_file>")
                list_backups()
        
        elif command == "list":
            list_backups()
        
        elif command == "stats" or command == "summary":
            show_stats_summary()
        
        elif command == "clean":
            keep = 10
            if len(sys.argv) > 2:
                try:
                    keep = int(sys.argv[2])
                except:
                    pass
            clean_old_backups(keep)
        
        else:
            print("Unknown command. Available commands:")
            print("  backup/create - Create new backup")
            print("  restore <file> - Restore from backup")
            print("  list - List all backups")
            print("  stats/summary - Show current stats summary")
            print("  clean [count] - Keep only N most recent backups (default: 10)")
    
    else:
        # Default action: create backup
        create_backup()
        print("\n💡 Tip: Use 'python railway_backup.py list' to see all backups")
