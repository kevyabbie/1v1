"""
COMPLETE DISCORD MATCHMAKING BOT - MAIN FILE
Combines all features from both bot versions
1v1, 2v2, 3v3, 4v4, and 5v5 Tournament
Optional socket server for remote control
Railway-compatible backup system (optional)
"""

import asyncio
import socket
import threading
import logging
import os
from typing import Optional, List
import traceback

import discord
from discord import app_commands

# Import the complete matchmaking setup
from team_matchmaking_part8 import setup_all_commands

# Try to import Railway backup system (optional)
BACKUP_AVAILABLE = False
try:
    from railway_backup import (
        setup_railway_backup_commands,
        railway_auto_backup_on_startup
    )
    BACKUP_AVAILABLE = True
    print("✅ Backup system loaded successfully")
except ImportError as e:
    print(f"⚠️  Backup system not available: {e}")
    print("   Bot will run without backup functionality")
    print("   To enable backups, add railway_backup.py to your project")

# ================= CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5050"))

# Validate token
if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
    raise ValueError("Please set DISCORD_TOKEN environment variable!")

# Socket server constants
MAX_CACHE_SIZE = 50
BUFFER_SIZE = 8192
MAX_CONNECTIONS = 5
ENABLE_SOCKET = os.getenv("ENABLE_SOCKET", "false").lower() == "true"

# BACKUP CHANNEL ID - CHANGE THIS TO YOUR BACKUP CHANNEL!
# To get your channel ID:
# 1. Create a private channel in your Discord server (e.g., #bot-backups)
# 2. Right-click the channel > Copy ID
# 3. Paste the ID below
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID", "0"))

# =========================================

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompleteDiscordBot:
    """Complete Discord bot with all matchmaking systems and optional socket server"""
    
    def __init__(self, token: str, host: str, port: int, enable_socket: bool, backup_channel_id: int):
        self.token = token
        self.host = host
        self.port = port
        self.enable_socket = enable_socket
        self.backup_channel_id = backup_channel_id
        
        # State management
        self.active_server: Optional[discord.Guild] = None
        self.active_channel: Optional[discord.TextChannel] = None
        self.message_cache: List[discord.Message] = []
        
        # Setup Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # Store all systems
        self.bot_systems = {}
        
        self._setup_events()
    
    def _setup_events(self):
        """Register Discord event handlers"""
        
        @self.client.event
        async def on_ready():
            """Called when bot is ready"""
            logger.info("="*60)
            logger.info("🚀 DISCORD MATCHMAKING BOT STARTING")
            logger.info("="*60)
            logger.info(f"✅ Logged in as {self.client.user}")
            logger.info(f"📊 Bot ID: {self.client.user.id}")
            logger.info(f"🌐 Connected to {len(self.client.guilds)} guild(s)")
            
            # Set active server/channel for socket commands
            if self.client.guilds:
                self.active_server = self.client.guilds[0]
                if self.active_server.text_channels:
                    self.active_channel = self.active_server.text_channels[0]
                logger.info(f"📍 Active Channel: #{self.active_channel.name}")
            
            logger.info("="*60)
            
            try:
                # Setup ALL matchmaking systems
                logger.info("⚙️  Setting up matchmaking systems...")
                logger.info("   - 1v1 Matchmaking System")
                logger.info("   - 2v2 Team System")
                logger.info("   - 3v3 Team System")
                logger.info("   - 4v4 Team System")
                logger.info("   - 5v5 Tournament System")
                logger.info("   - Party Management System")
                logger.info("   - Multi-Mode Stats System")
                logger.info("   - Profile Customization System")
                
                systems = setup_all_commands(self.client, self.tree)
                self.bot_systems.update(systems)
                
                logger.info("✅ All systems initialized successfully")
                
                # Setup Railway backup commands (if available)
                if BACKUP_AVAILABLE and self.backup_channel_id > 0:
                    logger.info("⚙️  Setting up backup system...")
                    setup_railway_backup_commands(
                        self.tree,
                        self.client,
                        self.backup_channel_id
                    )
                    logger.info("✅ Backup system initialized")
                elif not BACKUP_AVAILABLE:
                    logger.warning("⚠️  Backup system not available (railway_backup.py not found)")
                elif self.backup_channel_id == 0:
                    logger.warning("⚠️  BACKUP_CHANNEL_ID not set! Backups disabled.")
                    logger.warning("   Set BACKUP_CHANNEL_ID environment variable to enable backups.")
                
                # Sync commands to Discord
                logger.info("🔄 Syncing slash commands to Discord...")
                synced = await self.tree.sync()
                logger.info(f"✅ Synced {len(synced)} command(s)")
                
                # Show commands
                for i, cmd in enumerate(synced[:20], 1):
                    logger.info(f"   {i}. /{cmd.name}")
                if len(synced) > 20:
                    logger.info(f"   ... and {len(synced) - 20} more commands")
                
                # Create automatic backup (Railway-compatible) - if available
                if BACKUP_AVAILABLE and self.backup_channel_id > 0:
                    logger.info("="*60)
                    logger.info("📦 Creating automatic backup and notifying users...")
                    try:
                        # Get notification channel ID from environment or use backup channel
                        notification_channel_id = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))
                        if notification_channel_id == 0:
                            notification_channel_id = self.backup_channel_id
                        
                        await railway_auto_backup_on_startup(
                            self.client,
                            self.backup_channel_id,
                            notification_channel_id
                        )
                        logger.info("✅ Backup complete and users notified!")
                    except Exception as e:
                        logger.error(f"❌ Backup failed: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error during setup: {e}")
                logger.error(traceback.format_exc())
                return
            
            # Start socket server if enabled
            if self.enable_socket:
                loop = asyncio.get_event_loop()
                threading.Thread(
                    target=self._socket_server,
                    args=(loop,),
                    daemon=True
                ).start()
                logger.info(f"🔌 Socket server enabled on {self.host}:{self.port}")
            
            logger.info("="*60)
            logger.info("🤖 BOT IS FULLY OPERATIONAL!")
            logger.info("="*60)
        
        @self.client.event
        async def on_guild_join(guild):
            """Called when bot joins a new server"""
            logger.info(f"📥 Joined new guild: {guild.name} (ID: {guild.id})")
            logger.info(f"   Members: {guild.member_count}")
        
        @self.client.event
        async def on_guild_remove(guild):
            """Called when bot leaves a server"""
            logger.info(f"📤 Left guild: {guild.name} (ID: {guild.id})")
        
        @self.client.event
        async def on_message(message):
            """Handle incoming Discord messages"""
            if message.author == self.client.user:
                return
            
            # Cache message
            self.message_cache.append(message)
            self.message_cache = self.message_cache[-MAX_CACHE_SIZE:]
            
            # Log message
            server_name = message.guild.name if message.guild else "DM"
            channel_name = message.channel.name if hasattr(message.channel, "name") else "DM"
            
            header = f"[{server_name} -> #{channel_name}]"
            if self.client.user in message.mentions:
                logger.info(f"{header} [MENTION] {message.author}: {message.content}")
            else:
                logger.debug(f"{header} {message.author}: {message.content}")
        
        @self.client.event
        async def on_error(event, *args, **kwargs):
            """Global error handler"""
            logger.error(f"❌ Error in {event}:")
            logger.error(traceback.format_exc())
        
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            """Handle slash command errors"""
            logger.error(f"❌ Command error in /{interaction.command.name}: {error}")
            logger.error(traceback.format_exc())
            
            try:
                error_message = f"❌ An error occurred: {str(error)}"
                if interaction.response.is_done():
                    await interaction.followup.send(error_message, ephemeral=True)
                else:
                    await interaction.response.send_message(error_message, ephemeral=True)
            except:
                pass
    
    async def send_message(self, text: str) -> bool:
        """Send a message to the active channel"""
        if not self.active_channel:
            logger.error("No channel selected")
            return False
        
        try:
            await self.active_channel.send(text)
            logger.info(f"[YOU] #{self.active_channel.name}: {text}")
            return True
        except discord.Forbidden:
            logger.error("Missing permissions to send message")
            return False
        except discord.HTTPException as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def _socket_server(self, loop: asyncio.AbstractEventLoop):
        """Run socket server for remote control"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(MAX_CONNECTIONS)
            logger.info(f"🔌 Socket server listening on {self.host}:{self.port}")
            
            while True:
                try:
                    conn, addr = sock.accept()
                    self._handle_connection(conn, loop)
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
        
        except Exception as e:
            logger.critical(f"Socket server failed to start: {e}")
    
    def _handle_connection(self, conn: socket.socket, loop: asyncio.AbstractEventLoop):
        """Handle a single socket connection"""
        try:
            data = conn.recv(BUFFER_SIZE).decode('utf-8', errors='replace').strip()
            
            if not data:
                return
            
            response = self._process_command(data, loop)
            
            if response:
                conn.sendall(response.encode('utf-8'))
        
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        
        finally:
            try:
                conn.close()
            except:
                pass
    
    def _process_command(self, data: str, loop: asyncio.AbstractEventLoop) -> str:
        """Process socket command and return response"""
        
        if data == "/servers":
            msg = "Servers:\n"
            for i, guild in enumerate(self.client.guilds, 1):
                msg += f"{i}. {guild.name}\n"
            return msg
        
        if data.startswith("/status "):
            msg_text = data.split(" ", 1)[1]
            asyncio.run_coroutine_threadsafe(
                self.client.change_presence(activity=discord.Game(name=msg_text)),
                loop
            )
            return "Status updated\n"
        
        if data.startswith("/channel "):
            try:
                channel_id = int(data.split(" ", 1)[1])
                for guild in self.client.guilds:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        self.active_channel = channel
                        return f"Active channel set to #{channel.name}\n"
                return "Channel not found\n"
            except ValueError:
                return "Invalid channel ID\n"
        
        if data == "/help":
            return ("Socket Commands:\n"
                    "/servers - List servers\n"
                    "/status <text> - Set bot status\n"
                    "/channel <id> - Set active channel\n"
                    "/help - Show this help\n"
                    "<text> - Send message to active channel\n")
        
        if data.strip() and self.active_channel:
            asyncio.run_coroutine_threadsafe(self.send_message(data), loop)
            return ""
        
        return "Unknown command. Type /help for commands.\n"
    
    def run(self):
        """Start the bot"""
        try:
            logger.info("🔌 Connecting to Discord...")
            self.client.run(self.token)
        except discord.LoginFailure:
            logger.critical("❌ Invalid Discord token!")
            logger.critical("Please check your DISCORD_TOKEN environment variable")
        except Exception as e:
            logger.critical(f"❌ Failed to start bot: {e}")
            logger.critical(traceback.format_exc())


def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("COMPLETE DISCORD MATCHMAKING BOT")
    logger.info("All Game Modes | Profile System | Admin Tools")
    logger.info("="*60)
    
    if not BACKUP_AVAILABLE:
        logger.warning("="*60)
        logger.warning("⚠️  BACKUP SYSTEM NOT LOADED")
        logger.warning("="*60)
        logger.warning("The railway_backup.py file was not found.")
        logger.warning("Bot will run WITHOUT backup functionality.")
        logger.warning("")
        logger.warning("To enable backups:")
        logger.warning("1. Add railway_backup.py to your project")
        logger.warning("2. Create a backup channel and get its ID")
        logger.warning("3. Set BACKUP_CHANNEL_ID environment variable")
        logger.warning("="*60)
    elif BACKUP_CHANNEL_ID == 0:
        logger.warning("="*60)
        logger.warning("⚠️  BACKUP_CHANNEL_ID NOT SET!")
        logger.warning("="*60)
        logger.warning("Backups are DISABLED!")
        logger.warning("")
        logger.warning("To enable backups:")
        logger.warning("1. Create a private channel in your Discord server")
        logger.warning("2. Right-click the channel > Copy ID")
        logger.warning("3. Set environment variable:")
        logger.warning("   BACKUP_CHANNEL_ID=<your_channel_id>")
        logger.warning("="*60)
    
    bot = CompleteDiscordBot(TOKEN, HOST, PORT, ENABLE_SOCKET, BACKUP_CHANNEL_ID)
    bot.run()


if __name__ == "__main__":
    main()
