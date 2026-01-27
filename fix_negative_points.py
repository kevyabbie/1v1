#!/usr/bin/env python3
"""
Fix Negative Points Script
Run this script to fix any negative points in player_stats.json
"""

import json
import os
from pathlib import Path

def fix_negative_points(stats_file="player_stats.json"):
    """Load stats file and fix any negative points"""
    
    if not os.path.exists(stats_file):
        print(f"❌ {stats_file} not found!")
        return False
    
    try:
        # Load existing stats
        with open(stats_file, 'r') as f:
            data = json.load(f)
        
        print(f"📊 Found {len(data)} players")
        
        # Fix negative points
        fixed_count = 0
        for user_id, stats in data.items():
            if stats['points'] < 0:
                old_points = stats['points']
                stats['points'] = 0
                fixed_count += 1
                print(f"✅ Fixed {stats['username']}: {old_points} → 0 points")
        
        if fixed_count > 0:
            # Save corrected stats
            with open(stats_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n✅ Fixed {fixed_count} player(s) with negative points")
            print(f"💾 Saved to {stats_file}")
        else:
            print("\n✅ No negative points found - all players are at 0 or above!")
        
        # Display leaderboard
        print("\n" + "="*50)
        print("🏆 CURRENT LEADERBOARD (Top 10)")
        print("="*50)
        
        sorted_players = sorted(
            data.values(),
            key=lambda x: x['points'],
            reverse=True
        )[:10]
        
        for i, player in enumerate(sorted_players, 1):
            print(f"{i}. {player['username']}")
            print(f"   Points: {player['points']} | W/L: {player['wins']}/{player['losses']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Fixing Negative Points in Leaderboard")
    print("="*50)
    fix_negative_points()
