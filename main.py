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
        await interaction.response.send_message('Restart confirmed.', ephemeral=True)
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

# Keep track of when command(s) are run, only allow once per 5min interval
last_run_light = datetime.datetime(1990, 1, 1)
last_run_heavy = datetime.datetime(1990, 1, 1)


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


@client.tree.command()
@app_commands.choices(server=[
    app_commands.Choice(name='Light', value=1),
    app_commands.Choice(name='Heavy', value=2),
])
@app_commands.describe(
    server='Which server should revieve this message?',
    message='What would you like to say.',
)
async def send_message(interaction: discord.Interaction, server: app_commands.Choice[int], message: str):
    """Send a message to everyone in the server."""

    # Only discord mods can use the command
    # This gets taken care of when setuping up bot but its nice to have still
    # Oh also the framwork has a special check function to do this already I should use
    if interaction.user.get_role(MOD_ROLE_ID) == None:
        await interaction.response.send_message('You are not worthy.', ephemeral=True)
        return

    # Respond to request to tell the user to wait a moment
    # This def needs to be called before doing work that takes time,
    # but I wonder if it may as well be first line of the function?
    await interaction.response.defer()

    # Send command and respond to result
    server_msg = '\'servermsg \"' + message + '\"\''
    destination_server = server.name.lower()
    cmd = ["runuser", f"pzserver{destination_server}", "-c",
           f"/home/pzserver{destination_server}/pzserver send {server_msg}"]
    response = subprocess.run(cmd, capture_output=True)
    last_line = response.stdout.decode("utf-8").split('\r')[-1]
    status = f'Sent to {destination_server} server:\n> {message}' if 'OK' in last_line else 'Something wrong maybe\n' + last_line

    # TODO: Figure out the logging module instead of printing
    print(response)
    await interaction.followup.send(status)


@client.tree.command()
@app_commands.choices(server=[
    app_commands.Choice(name='Light', value=1),
    app_commands.Choice(name='Heavy', value=2),
])
async def restart_server(interaction: discord.Interaction, server: app_commands.Choice[int]):
    """Restarts the server!!!"""

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message('You are not worthy.', ephemeral=True)
        return

    destination_server = server.name.lower()

    # Place rate limit the command
    global last_run_light, last_run_heavy
    last_run = last_run_light if destination_server == 'light' else last_run_heavy
    elapsed_time = datetime.datetime.now() - last_run
    if elapsed_time.seconds < 300:
        await interaction.response.send_message(f'Please wait {300 - elapsed_time.seconds} more seconds.', ephemeral=True)
        return

    # Send the question with buttons
    view = Confirm()
    await interaction.response.send_message(f'Restart {destination_server} server?', view=view, ephemeral=True)
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
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(f'{destination_server.capitalize()} server restart initiated by {interaction.user.display_name}...')

        # Update last run time of command
        if destination_server == 'light':
            last_run_light = datetime.datetime.now()
        elif destination_server == 'heavy':
            last_run_heavy = datetime.datetime.now()

        cmd = ["systemctl", "restart", f"pzserver{destination_server}"]
        response = subprocess.run(cmd)

        if response.returncode == 0:
            status = f'Success! The **{destination_server}** server was shut down and is now starting back up.'
        else:
            status = 'Something wrong maybe...\n' + response.returncode

        # # TODO: Figure out the logging module instead of printing
        print(response)

        # Announce restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(status)
    else:
        print('Cancelled...')


if __name__ == '__main__':
    client.run(os.getenv('TOKEN'))
