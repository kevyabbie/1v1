import asyncio
import socket
import threading
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, List
import traceback

import discord
from discord import app_commands
from gtts import gTTS

# Import the matchmaking system
from matchmaking_system import setup_matchmaking

# ================= CONFIG =================
# PUT YOUR TOKEN HERE:
TOKEN = "MTQ2MDQ0MDk5NzE5OTYxNDA0Nw.GdT5PR.AsGY-9J9_Jq7LGjHx6XXGnyLlnhMzFo2h5X908"
HOST = "127.0.0.1"
PORT = 5050

# Validate token
if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
    raise ValueError("Please set your Discord token in the TOKEN variable!")

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
    """Discord bot with socket-based control interface and 1v1 matchmaking."""
    
    def __init__(self, token: str, host: str, port: int):
        self.token = token
        self.host = host
        self.port = port
        
        # State management
        self.active_server: Optional[discord.Guild] = None
        self.active_channel: Optional[discord.TextChannel] = None
        self.message_cache: List[discord.Message] = []
        
        # Setup Discord client with app commands
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
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
            
            # Setup and sync slash commands
            self.matchmaking = setup_matchmaking(self.client, self.tree)
            
            try:
                # Sync commands globally
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
            
            # Start socket server in background thread
            loop = asyncio.get_event_loop()
            threading.Thread(
                target=self._socket_server,
                args=(loop,),
                daemon=True
            ).start()
        
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
            
            header = f"\n\033[36m[{server_name} -> #{channel_name}]\033[0m"
            if self.client.user in message.mentions:
                logger.info(f"{header} \033[1;31m[MENTION]\033[0m {message.author}: {message.content}")
            else:
                logger.info(f"{header} {message.author}: {message.content}")
            
            # Log attachments and stickers
            for att in message.attachments:
                logger.info(f"\033[34m[ATTACHMENT]\033[0m {att.filename} {att.url}")
            for st in message.stickers:
                logger.info(f"\033[35m[STICKER]\033[0m {st.name}")
    
    async def send_message(self, text: str) -> bool:
        """Send a message to the active channel."""
        if not self.active_channel:
            logger.error("No channel selected")
            return False
        
        try:
            await self.active_channel.send(text)
            logger.info(f"\033[32m[YOU]\033[0m #{self.active_channel.name}: {text}")
            return True
        except discord.Forbidden:
            logger.error("Missing permissions to send message")
            return False
        except discord.HTTPException as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def send_tag(self, username: str, msg: str) -> bool:
        """Tag a user in the active channel."""
        if not self.active_server or not self.active_channel:
            logger.error("No server or channel selected")
            return False
        
        for member in self.active_server.members:
            if member.name == username:
                try:
                    await self.active_channel.send(f"{member.mention} {msg}")
                    return True
                except discord.HTTPException as e:
                    logger.error(f"Failed to tag user: {e}")
                    return False
        
        logger.warning(f"User '{username}' not found")
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
                    logger.error(traceback.format_exc())
        
        except Exception as e:
            logger.critical(f"Socket server failed to start: {e}")
            logger.critical(traceback.format_exc())
    
    def _handle_connection(self, conn: socket.socket, loop: asyncio.AbstractEventLoop):
        """Handle a single socket connection."""
        try:
            data = conn.recv(BUFFER_SIZE).decode('utf-8', errors='replace').strip()
            
            if not data:
                return
            
            response = self._process_command(data, loop)
            
            if response:
                conn.sendall(response.encode('utf-8'))
        
        except UnicodeDecodeError as e:
            logger.error(f"Invalid UTF-8 data received: {e}")
            try:
                conn.sendall(b"Error: Invalid encoding\n")
            except:
                pass
        
        except socket.error as e:
            logger.error(f"Socket error: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error handling connection: {e}")
            logger.error(traceback.format_exc())
            try:
                conn.sendall(b"Internal error\n")
            except:
                pass
        
        finally:
            try:
                conn.close()
            except:
                pass
    
    def _process_command(self, data: str, loop: asyncio.AbstractEventLoop) -> str:
        """Process a command and return response."""
        
        # ---------- SERVERS ----------
        if data == "/servers":
            msg = "Servers:\n"
            for i, guild in enumerate(self.client.guilds, 1):
                msg += f"{i}. {guild.name}\n"
            return msg
        
        # ---------- USE SERVER ----------
        if data.startswith("/use "):
            arg = data.split(" ", 1)[1]
            servers = list(self.client.guilds)
            server_found = None
            
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(servers):
                    server_found = servers[idx]
            else:
                for guild in servers:
                    if guild.name == arg:
                        server_found = guild
                        break
            
            if server_found:
                self.active_server = server_found
                self.active_channel = (
                    self.active_server.text_channels[0] 
                    if self.active_server.text_channels 
                    else None
                )
                return f"Using server: {self.active_server.name}\n"
            else:
                return "Server not found\n"
        
        # ---------- LIST CHANNELS ----------
        if data == "/list":
            if not self.active_server:
                return "No server selected\n"
            
            msg = "Channels:\n"
            for i, ch in enumerate(self.active_server.channels, 1):
                if isinstance(ch, discord.TextChannel):
                    kind = "Text"
                elif isinstance(ch, discord.VoiceChannel):
                    kind = "Voice"
                elif isinstance(ch, discord.CategoryChannel):
                    kind = "Category"
                else:
                    kind = "Forum"
                msg += f"{i}. {ch.name} -> ID: {ch.id} ({kind})\n"
            return msg
        
        # ---------- CHANNEL BY INDEX OR NAME ----------
        if data.startswith("/channel "):
            if not self.active_server:
                return "No server selected\n"
            
            arg = data.split(" ", 1)[1]
            text_channels = [
                c for c in self.active_server.channels 
                if isinstance(c, discord.TextChannel)
            ]
            channel_found = None
            
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(text_channels):
                    channel_found = text_channels[idx]
            
            if not channel_found:
                for ch in text_channels:
                    if ch.name == arg:
                        channel_found = ch
                        break
            
            if channel_found:
                self.active_channel = channel_found
                return f"Channel set to #{self.active_channel.name}\n"
            else:
                return "Invalid channel (use number or name)\n"
        
        # ---------- CHANNEL BY ID ----------
        if data.startswith("/channelid "):
            if not self.active_server:
                return "No server selected\n"
            
            arg = data.split(" ", 1)[1]
            try:
                channel_id = int(arg)
                for ch in self.active_server.channels:
                    if ch.id == channel_id:
                        if isinstance(ch, discord.TextChannel):
                            self.active_channel = ch
                            return f"Text channel set to #{ch.name} (ID: {ch.id})\n"
                        elif isinstance(ch, discord.VoiceChannel):
                            return f"Voice channel detected: {ch.name} (ID: {ch.id})\n"
                        else:
                            return "Channel type not supported\n"
            except ValueError:
                pass
            
            return "Invalid channel ID\n"
        
        # ---------- SHOW CHANNEL IDS ----------
        if data == "/showchannelid":
            if not self.active_server:
                return "No server selected\n"
            
            msg = f"All channels in {self.active_server.name}:\n"
            for ch in self.active_server.channels:
                if isinstance(ch, discord.TextChannel):
                    kind = "Text"
                elif isinstance(ch, discord.VoiceChannel):
                    kind = "Voice"
                elif isinstance(ch, discord.CategoryChannel):
                    kind = "Category"
                else:
                    kind = "Forum"
                msg += f"{kind}: {ch.name} -> ID: {ch.id}\n"
            return msg
        
        # ---------- WHO ----------
        if data == "/who":
            if not self.active_server or not self.active_channel:
                return "No channel selected\n"
            
            users = [m.name for m in self.active_channel.members]
            return f"Users in #{self.active_channel.name}:\n" + "\n".join(users) + "\n"
        
        # ---------- DM ----------
        if data.startswith("/dm "):
            parts = data.split(" ", 2)
            if len(parts) < 3:
                return "Usage: /dm <username> <msg>\n"
            
            username, msg_text = parts[1], parts[2]
            user_found = None
            
            for user in self.client.users:
                if user.name == username:
                    user_found = user
                    break
            
            if not user_found:
                return "User not found\n"
            
            asyncio.run_coroutine_threadsafe(user_found.send(msg_text), loop)
            return "DM sent\n"
        
        # ---------- TAG ----------
        if data.startswith("/tag "):
            try:
                _, username, msg_text = data.split(" ", 2)
                asyncio.run_coroutine_threadsafe(
                    self.send_tag(username, msg_text), 
                    loop
                )
                return "User tagged\n"
            except ValueError:
                return "Usage: /tag <username> <msg>\n"
        
        # ---------- EVERYONE ----------
        if data.startswith("/everyone "):
            if not self.active_server or not self.active_channel:
                return "No channel selected\n"
            
            msg_text = data.split(" ", 1)[1]
            asyncio.run_coroutine_threadsafe(
                self.send_message(f"@everyone {msg_text}"), 
                loop
            )
            return "Everyone tagged\n"
        
        # ---------- STATUS ----------
        if data.startswith("/status "):
            msg_text = data.split(" ", 1)[1]
            asyncio.run_coroutine_threadsafe(
                self.client.change_presence(activity=discord.Game(name=msg_text)),
                loop
            )
            return "Status updated\n"
        
        # ---------- HISTORY ----------
        if data.startswith("/history"):
            parts = data.split()
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            recent = self.message_cache[-n:]
            
            msg = "Last messages:\n"
            for i, message in enumerate(recent, 1):
                msg += f"{i}. [{message.author}] #{message.channel.name}: {message.content}\n"
            return msg
        
        # ---------- REPLY ----------
        if data.startswith("/reply"):
            parts = data.split(" ", 2)
            if len(parts) < 3 or not parts[1].isdigit():
                return "Usage: /reply <number> <text>\n"
            
            idx = int(parts[1]) - 1
            text = parts[2]
            
            if 0 <= idx < len(self.message_cache):
                asyncio.run_coroutine_threadsafe(
                    self.message_cache[idx].reply(text), 
                    loop
                )
                return "Reply sent\n"
            else:
                return "Invalid message number\n"
        
        # ---------- VOICE JOIN ----------
        if data.startswith("/joinvoice "):
            if not self.active_server:
                return "No server selected\n"
            
            arg = data.split(" ", 1)[1]
            voice_channel = None
            
            try:
                channel_id = int(arg)
                for ch in self.active_server.channels:
                    if isinstance(ch, discord.VoiceChannel) and ch.id == channel_id:
                        voice_channel = ch
                        break
            except ValueError:
                return "Invalid voice channel ID\n"
            
            if voice_channel:
                async def join_vc():
                    try:
                        await voice_channel.connect()
                        return f"Joined voice channel: {voice_channel.name}\n"
                    except discord.ClientException as e:
                        return f"Already connected or error: {e}\n"
                    except Exception as e:
                        return f"Failed to join voice channel: {e}\n"
                
                future = asyncio.run_coroutine_threadsafe(join_vc(), loop)
                try:
                    return future.result(timeout=5)
                except TimeoutError:
                    return "Timeout joining voice channel\n"
            else:
                return "Invalid voice channel ID\n"
        
        # ---------- VOICE LEAVE ----------
        if data == "/leavevoice":
            async def leave_vc():
                for vc in self.client.voice_clients:
                    if vc.guild == self.active_server:
                        await vc.disconnect()
                        return f"Left voice channel in {self.active_server.name}\n"
                return "Not connected to any voice channel\n"
            
            future = asyncio.run_coroutine_threadsafe(leave_vc(), loop)
            try:
                return future.result(timeout=5)
            except TimeoutError:
                return "Timeout leaving voice channel\n"
        
        # ---------- TTS ----------
        if data.startswith("/tts "):
            if not self.active_server:
                return "No server selected\n"
            
            parts = data.split(" ", 2)
            if len(parts) < 3:
                return "Usage: /tts <lang> <text>\n"
            
            lang, text = parts[1], parts[2]
            
            async def tts_play():
                vc = None
                for client_vc in self.client.voice_clients:
                    if client_vc.guild == self.active_server:
                        vc = client_vc
                        break
                
                if not vc:
                    return "Bot not connected to a voice channel\n"
     
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tts_file = tmp.name
                
                try:
                    gTTS(text=text, lang=lang).save(tts_file)
                    
         
                    if vc.is_playing():
                        vc.stop()
                  
                    vc.play(discord.FFmpegPCMAudio(tts_file))
                    
                    return f"TTS played in {vc.channel.name} (lang={lang})\n"
                
                finally:
       
                    await asyncio.sleep(2)
                    try:
                        Path(tts_file).unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"Failed to delete TTS file: {e}")
            
            future = asyncio.run_coroutine_threadsafe(tts_play(), loop)
            try:
                return future.result(timeout=10)
            except TimeoutError:
                return "Timeout playing TTS\n"
        
    
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
    logger.info("Starting Discord bot with 1v1 matchmaking...")
    bot = DiscordBot(TOKEN, HOST, PORT)
    bot.run()


if __name__ == "__main__":
    main()
