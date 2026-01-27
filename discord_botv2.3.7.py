import asyncio
import socket
import threading
import logging
import os
from typing import Optional, List
import traceback

import discord
from discord import app_commands

# Import the matchmaking system
from matchmaking_system import setup_matchmaking

# ================= CONFIG =================
# Railway will use environment variables
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5050"))

# Validate token
if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
    raise ValueError("Please set DISCORD_TOKEN environment variable!")

# Constants
MAX_CACHE_SIZE = 50
BUFFER_SIZE = 8192
MAX_CONNECTIONS = 5
# =========================================

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DiscordBot:
    """Discord bot with 1v1 matchmaking (NO VOICE FEATURES)."""
    
    def __init__(self, token: str, host: str, port: int):
        self.token = token
        self.host = host
        self.port = port
        
        # State management
        self.active_server: Optional[discord.Guild] = None
        self.active_channel: Optional[discord.TextChannel] = None
        self.message_cache: List[discord.Message] = []
        
        # Setup Discord client WITHOUT voice intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # Setup matchmaking system
        self.matchmaking = None
        
        self._setup_events()
    
    def _setup_events(self):
        """Register Discord event handlers."""
        
        @self.client.event
        async def on_ready():
            """Called when bot is ready."""
            if self.client.guilds:
                self.active_server = self.client.guilds[0]
                if self.active_server.text_channels:
                    self.active_channel = self.active_server.text_channels[0]
            
            logger.info(f"Bot logged in as {self.client.user}")
            logger.info(f"Bot is in {len(self.client.guilds)} guild(s)")
            
            # Setup and sync slash commands
            self.matchmaking = setup_matchmaking(self.client, self.tree)
            
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
            
            # Socket server (optional)
            if os.getenv("ENABLE_SOCKET", "false").lower() == "true":
                loop = asyncio.get_event_loop()
                threading.Thread(
                    target=self._socket_server,
                    args=(loop,),
                    daemon=True
                ).start()
                logger.info("Socket server enabled")
        
        @self.client.event
        async def on_message(message):
            """Handle incoming Discord messages."""
            if message.author == self.client.user:
                return
            
            # Cache message
            self.message_cache.append(message)
            self.message_cache = self.message_cache[-MAX_CACHE_SIZE:]
            
            # Format output
            server_name = message.guild.name if message.guild else "DM"
            channel_name = message.channel.name if hasattr(message.channel, "name") else "DM"
            
            header = f"[{server_name} -> #{channel_name}]"
            if self.client.user in message.mentions:
                logger.info(f"{header} [MENTION] {message.author}: {message.content}")
            else:
                logger.info(f"{header} {message.author}: {message.content}")
    
    async def send_message(self, text: str) -> bool:
        """Send a message to the active channel."""
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
        """Run socket server for receiving commands."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(MAX_CONNECTIONS)
            logger.info(f"Socket server listening on {self.host}:{self.port}")
            
            while True:
                try:
                    conn, addr = sock.accept()
                    self._handle_connection(conn, loop)
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
        
        except Exception as e:
            logger.critical(f"Socket server failed to start: {e}")
    
    def _handle_connection(self, conn: socket.socket, loop: asyncio.AbstractEventLoop):
        """Handle a single socket connection."""
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
        """Process a command and return response."""
        
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
        
        if data.strip() and self.active_channel:
            asyncio.run_coroutine_threadsafe(self.send_message(data), loop)
            return ""
        
        return "Unknown command\n"
    
    def run(self):
        """Start the bot."""
        try:
            self.client.run(self.token)
        except discord.LoginFailure:
            logger.critical("Invalid Discord token!")
        except Exception as e:
            logger.critical(f"Failed to start bot: {e}")
            logger.critical(traceback.format_exc())


def main():
    """Main entry point."""
    logger.info("Starting Discord 1v1 Matchmaking Bot...")
    logger.info("Voice features disabled - matchmaking only")
    bot = DiscordBot(TOKEN, HOST, PORT)
    bot.run()


if __name__ == "__main__":
    main()
