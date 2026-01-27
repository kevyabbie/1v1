"""
MAIN BOT FILE
Complete Discord bot with all matchmaking systems
1v1, 2v2, 3v3, 4v4, and 5v5 Tournament
"""
import discord
from discord import app_commands
import os
import logging
import traceback

from team_matchmaking_part8 import setup_all_commands

TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")

if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
    raise ValueError("Please set DISCORD_TOKEN environment variable!")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("="*60)
    logger.info("Starting Discord Matchmaking Bot")
    logger.info("="*60)
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    bot_systems = {}
    
    @client.event
    async def on_ready():
        logger.info("="*60)
        logger.info(f"Logged in as {client.user}")
        logger.info(f"Bot ID: {client.user.id}")
        logger.info(f"Connected to {len(client.guilds)} guild(s)")
        logger.info("="*60)
        
        try:
            logger.info("Setting up matchmaking systems...")
            logger.info(" - 1v1 System")
            logger.info(" - 2v2 System")
            logger.info(" - 3v3 System")
            logger.info(" - 4v4 System")
            logger.info(" - 5v5 Tournament System")
            logger.info(" - Party System")
            logger.info(" - Multi-Mode Stats")
            
            systems = setup_all_commands(client, tree)
            bot_systems.update(systems)
            
            logger.info("All systems initialized")
            logger.info("Syncing slash commands to Discord...")
            synced = await tree.sync()
            logger.info(f"Synced {len(synced)} command(s):")
            
            for i, cmd in enumerate(synced[:15], 1):
                logger.info(f"  {i}. /{cmd.name}")
            if len(synced) > 15:
                logger.info(f"  ... and {len(synced) - 15} more")
        
        except Exception as e:
            logger.error(f"Error during setup: {e}")
            logger.error(traceback.format_exc())
            return
        
        logger.info("="*60)
        logger.info("BOT IS FULLY OPERATIONAL!")
        logger.info("="*60)
    
    @client.event
    async def on_guild_join(guild):
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        logger.info(f"  Members: {guild.member_count}")
    
    @client.event
    async def on_guild_remove(guild):
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    @client.event
    async def on_error(event, *args, **kwargs):
        logger.error(f"Error in {event}:")
        logger.error(traceback.format_exc())
    
    @tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.error(f"Command error in /{interaction.command.name}: {error}")
        logger.error(traceback.format_exc())
        
        try:
            error_message = f"An error occurred: {str(error)}"
            if interaction.response.is_done():
                await interaction.followup.send(error_message, ephemeral=True)
            else:
                await interaction.response.send_message(error_message, ephemeral=True)
        except:
            pass
    
    try:
        logger.info("Connecting to Discord...")
        client.run(TOKEN)
    except discord.LoginFailure:
        logger.critical("Invalid Discord token!")
        logger.critical("Please check your DISCORD_TOKEN environment variable")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    main()
