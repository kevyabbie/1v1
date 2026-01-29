#!/usr/bin/env python3
"""
Railway Backup Script
Backs up all player data files to timestamped backups
"""

import json
import os
from datetime import datetime
from pathlib import Path
import shutil


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
    
    return backed_up > 0


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
        return
    
    backups = sorted(backup_dir.glob("*.json"), reverse=True)
    
    if not backups:
        print("📁 No backups found")
        return
    
    print("=" * 60)
    print("📦 Available Backups:")
    print("=" * 60)
    
    for backup in backups:
        size = backup.stat().st_size / 1024
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"📄 {backup.name}")
        print(f"   Size: {size:.2f} KB | Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("=" * 60)


def show_stats_summary():
    """Show summary of current stats"""
    
    print("=" * 60)
    print("📊 Current Stats Summary:")
    print("=" * 60)
    
    # Multi-mode stats
    if os.path.exists("multi_mode_stats.json"):
        try:
            with open("multi_mode_stats.json", 'r') as f:
                data = json.load(f)
                print("\n🎮 Multi-Mode Stats:")
                for mode, players in data.items():
                    print(f"   {mode}: {len(players)} players")
        except Exception as e:
            print(f"   ❌ Error reading multi_mode_stats.json: {e}")
    
    # Player profiles
    if os.path.exists("player_profiles.json"):
        try:
            with open("player_profiles.json", 'r') as f:
                data = json.load(f)
                print(f"\n👤 Player Profiles: {len(data)} profiles")
        except Exception as e:
            print(f"   ❌ Error reading player_profiles.json: {e}")
    
    print("=" * 60)


def clean_old_backups(keep_count: int = 10):
    """Keep only the most recent N backups"""
    
    backup_dir = Path("backups")
    
    if not backup_dir.exists():
        print("📁 No backups directory found")
        return
    
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
