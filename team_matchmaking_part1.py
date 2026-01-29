"""
TEAM MATCHMAKING SYSTEM - PART 1 (FIXED)
Party System with Party Name
Create parties, invite players, manage teams, set party names
"""

import discord
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class Party:
    """Represents a party/team"""
    def __init__(self, host: discord.Member):
        self.host = host
        self.members: List[discord.Member] = [host]
        self.pending_invites: Dict[int, datetime] = {}  # user_id -> invite_time
        self.created_at = datetime.now()
        self.max_size = 5
        self.party_name: str = f"{host.display_name}'s Party"  # NEW: Custom party name
    
    def set_party_name(self, name: str) -> bool:
        """Set custom party name"""
        if len(name) > 50:
            return False
        self.party_name = name
        return True
    
    def add_member(self, member: discord.Member) -> bool:
        """Add member to party"""
        if len(self.members) >= self.max_size:
            return False
        if member.id in [m.id for m in self.members]:
            return False
        self.members.append(member)
        return True
    
    def remove_member(self, member: discord.Member) -> bool:
        """Remove member from party"""
        if member.id == self.host.id:
            return False  # Can't remove host
        for m in self.members:
            if m.id == member.id:
                self.members.remove(m)
                return True
        return False
    
    def is_host(self, user: discord.Member) -> bool:
        """Check if user is host"""
        return user.id == self.host.id
    
    def is_member(self, user: discord.Member) -> bool:
        """Check if user is in party"""
        return user.id in [m.id for m in self.members]
    
    def get_size(self) -> int:
        """Get party size"""
        return len(self.members)


class PartySystem:
    """Manages all parties"""
    def __init__(self):
        self.parties: Dict[int, Party] = {}  # host_id -> Party
        self.user_party_map: Dict[int, int] = {}  # user_id -> host_id
    
    def create_party(self, host: discord.Member) -> Tuple[bool, str]:
        """Create a new party"""
        if host.id in self.user_party_map:
            return False, "You're already in a party!"
        
        party = Party(host)
        self.parties[host.id] = party
        self.user_party_map[host.id] = host.id
        return True, f"✅ Party created: **{party.party_name}**\nUse `/partyinvite @user` to invite members."
    
    def set_party_name(self, user: discord.Member, name: str) -> Tuple[bool, str]:
        """Set party name (anyone in party can change it)"""
        party = self.get_user_party(user)
        if not party:
            return False, "You're not in a party! Use `/party` to create one."
        
        if not party.set_party_name(name):
            return False, "Party name too long! (Max 50 characters)"
        
        return True, f"✅ Party name changed to: **{party.party_name}**"
    
    def get_user_party(self, user: discord.Member) -> Optional[Party]:
        """Get the party a user is in"""
        if user.id not in self.user_party_map:
            return None
        host_id = self.user_party_map[user.id]
        return self.parties.get(host_id)
    
    def invite_to_party(self, host: discord.Member, target: discord.Member) -> Tuple[bool, str]:
        """Invite user to party"""
        party = self.parties.get(host.id)
        if not party:
            return False, "You don't have a party! Use `/party` to create one."
        
        if not party.is_host(host):
            return False, "Only the host can invite members!"
        
        if party.get_size() >= party.max_size:
            return False, f"Party is full! (Max {party.max_size} members)"
        
        if target.id in self.user_party_map:
            return False, f"{target.display_name} is already in a party!"
        
        if target.id in party.pending_invites:
            return False, f"{target.display_name} already has a pending invite!"
        
        party.pending_invites[target.id] = datetime.now()
        return True, f"✅ Invited {target.mention} to the party!"
    
    def accept_invite(self, user: discord.Member, host: discord.Member) -> Tuple[bool, str]:
        """Accept party invite"""
        if user.id in self.user_party_map:
            return False, "You're already in a party!"
        
        party = self.parties.get(host.id)
        if not party:
            return False, "That party no longer exists!"
        
        if user.id not in party.pending_invites:
            return False, f"You don't have a pending invite from {host.display_name}!"
        
        if party.get_size() >= party.max_size:
            del party.pending_invites[user.id]
            return False, "Party is full!"
        
        # Accept invite
        party.add_member(user)
        del party.pending_invites[user.id]
        self.user_party_map[user.id] = host.id
        
        return True, f"✅ Joined **{party.party_name}**! ({party.get_size()}/{party.max_size})"
    
    def decline_invite(self, user: discord.Member, host: discord.Member) -> Tuple[bool, str]:
        """Decline party invite"""
        party = self.parties.get(host.id)
        if not party:
            return False, "That party no longer exists!"
        
        if user.id not in party.pending_invites:
            return False, f"You don't have a pending invite from {host.display_name}!"
        
        del party.pending_invites[user.id]
        return True, f"✅ Declined invite from {host.display_name}."
    
    def leave_party(self, user: discord.Member) -> Tuple[bool, str]:
        """Leave party"""
        party = self.get_user_party(user)
        if not party:
            return False, "You're not in a party!"
        
        if party.is_host(user):
            # Disband party
            for member in party.members:
                if member.id in self.user_party_map:
                    del self.user_party_map[member.id]
            del self.parties[user.id]
            return True, "✅ Party disbanded."
        
        # Remove member
        party.remove_member(user)
        del self.user_party_map[user.id]
        return True, f"✅ Left the party."
    
    def kick_member(self, host: discord.Member, target: discord.Member) -> Tuple[bool, str]:
        """Kick member from party"""
        party = self.parties.get(host.id)
        if not party:
            return False, "You don't have a party!"
        
        if not party.is_host(host):
            return False, "Only the host can kick members!"
        
        if target.id == host.id:
            return False, "You can't kick yourself! Use `/partydisband` instead."
        
        if not party.is_member(target):
            return False, f"{target.display_name} is not in your party!"
        
        party.remove_member(target)
        if target.id in self.user_party_map:
            del self.user_party_map[target.id]
        
        return True, f"✅ Kicked {target.display_name} from the party."
