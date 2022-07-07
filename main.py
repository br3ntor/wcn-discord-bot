import subprocess
import datetime
import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# replace with your guild id
MY_GUILD = discord.Object(id=int(os.getenv('MY_GUILD')))
MOD_ROLE_ID = int(os.getenv('MOD_ROLE_ID'))
ANNOUNCE_CHANNEL = int(os.getenv('ANNOUNCE_CHANNEL'))


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('The server will restart.', ephemeral=True)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label='No', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Restart canceled.', ephemeral=True)
        self.value = False
        self.stop()


intents = discord.Intents.default()
client = MyClient(intents=intents)

# Keep track of when commands are run, only allow once per 5min interval
last_run = datetime.datetime(1990, 1, 1)


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


@client.tree.command()
async def server_check(interaction: discord.Interaction):
    """Check status of server, restart if crashed."""

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) == None:
        await interaction.response.send_message('You are not worthy.', ephemeral=True)
        return

    # Rate limit the command
    global last_run
    elapsed_time = datetime.datetime.now() - last_run
    if elapsed_time.seconds < 300:
        await interaction.response.send_message(f'Please wait {300 - elapsed_time.seconds} more seconds.', ephemeral=True)
        return

    # Call the command and send the result
    # Update last_run before calling the command so var gets set ASAP
    last_run = datetime.datetime.now()
    await interaction.response.defer()
    cmd = ["/home/pzserver/pzserver", "monitor"]
    response = subprocess.run(cmd, capture_output=True)
    status = response.stdout.decode("utf-8")
    await interaction.followup.send(status)


@client.tree.command()
async def server_restart(interaction: discord.Interaction):
    """Restarts the server!!!"""

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) == None:
        await interaction.response.send_message('You are not worthy.', ephemeral=True)
        return

    # Place rate limit the command
    global last_run
    elapsed_time = datetime.datetime.now() - last_run
    if elapsed_time.seconds < 300:
        await interaction.response.send_message(f'Please wait {300 - elapsed_time.seconds} more seconds.', ephemeral=True)
        return

    # Send the question with buttons
    view = Confirm()
    await interaction.response.send_message('Restart server?', view=view, ephemeral=True)
    await view.wait()

    # Disable buttons after click
    for button in view.children:
        button.disabled = True
    original_message = await interaction.original_message()
    await original_message.edit(view=view)

    # Action taken based on interaction results
    if view.value is None:
        print('Timed out...')
    elif view.value:
        print('Confirmed...')
        # Call the restart command, assuming server is running.
        # If it's not running, command will prompt for yes or no to start server.
        # I am ignoring this unil I learn more how to deal with that.
        last_run = datetime.datetime.now()
        cmd = ["/home/pzserver/pzserver", "restart"]
        response = subprocess.run(cmd, capture_output=True)
        status = response.stdout.decode("utf-8")

        # Announce restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(status)
        # await interaction.followup.send(status)
    else:
        print('Cancelled...')


if __name__ == '__main__':
    client.run(os.getenv('TOKEN'))
