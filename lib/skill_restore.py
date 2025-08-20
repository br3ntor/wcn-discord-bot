import asyncio
import glob
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Callable, Coroutine, Dict, Optional, Tuple

from config import Config
from lib.game_db import get_player
from lib.pzserver import pz_send_command

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS

# XP tables for skill levels
PASSIVE_SKILL_XP = [
    0,
    1500,
    3000,
    6000,
    9000,
    18000,
    30000,
    60000,
    90000,
    120000,
    150000,
]
REGULAR_SKILL_XP = [0, 75, 150, 300, 750, 1500, 3000, 4500, 6000, 7500, 9000]

# Passive skills (these use the passive XP table)
PASSIVE_SKILLS = {"Fitness", "Strength"}


class LevelRestore:
    """
    Restores a player's skill levels to what they were before their most significant death.
    """

    def __init__(self, server_name: str, player_name: str) -> None:
        self.server_name = server_name
        self.player_name = player_name
        self.players_command_received = False
        self.addxp_commands_sent = 0
        self.addxp_commands_confirmed = 0
        self.log_file_path = (
            f"/home/{SYSTEM_USERS[server_name]}/log/console/pzserver-console.log"
        )
        self.perk_log_path = f"/home/{SYSTEM_USERS[server_name]}/Zomboid/Logs"

    def get_latest_perk_log(self) -> Optional[str]:
        """Find the most recent PerkLog file."""
        pattern = f"{self.perk_log_path}/*PerkLog.txt"
        perk_files = glob.glob(pattern)
        if not perk_files:
            return None
        # Sort by modification time and return the most recent
        return max(
            perk_files, key=lambda x: datetime.fromtimestamp(os.path.getmtime(x))
        )

    def parse_skill_line(self, line: str) -> Dict[str, int]:
        """Parse a skill line and return a dictionary of skill levels."""
        skills = {}
        # Find the skill data between the brackets
        match = re.search(r"\[([^\]]*)\]\[Hours Survived:", line)
        if match:
            skill_data = match.group(1)
            # Split by commas and parse each skill=level pair
            for skill_pair in skill_data.split(", "):
                if "=" in skill_pair:
                    skill, level = skill_pair.split("=")
                    skills[skill.strip()] = int(level.strip())
        return skills

    def get_xp_for_level(self, skill: str, level: int) -> int:
        """Get the total XP needed to reach a specific level."""
        if skill in PASSIVE_SKILLS:
            return sum(PASSIVE_SKILL_XP[1 : level + 1]) if level > 0 else 0
        else:
            return sum(REGULAR_SKILL_XP[1 : level + 1]) if level > 0 else 0

    def analyze_player_death(
        self,
    ) -> Tuple[Optional[Dict[str, int]], Optional[Dict[str, int]]]:
        """
        Analyze player's most significant death and return pre-death and current skill levels.
        Returns (pre_death_skills, current_skills) or (None, None) if no death found.
        """
        perk_log_file = self.get_latest_perk_log()
        if not perk_log_file:
            print("No PerkLog file found")
            return None, None

        try:
            with open(perk_log_file, "r") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading PerkLog file: {e}")
            return None, None

        # Filter lines for this player using player name
        player_lines = [
            line.strip() for line in lines if f"][{self.player_name}][" in line
        ]

        if not player_lines:
            print(f"No log entries found for player {self.player_name}")
            return None, None

        # Find all deaths and their hours survived
        deaths = []
        for i, line in enumerate(player_lines):
            if "[Died][Hours Survived:" in line:
                match = re.search(r"\[Died\]\[Hours Survived: (\d+)\]", line)
                if match:
                    deaths.append((i, int(match.group(1))))

        if not deaths:
            print("No death records found")
            return None, None

        # Find the death with the highest hours survived (most significant)
        most_significant_death = max(deaths, key=lambda x: x[1])
        death_line_index, death_hours = most_significant_death

        print(f"Most significant death at {death_hours} hours survived")

        # Find the last login before this death
        login_line_index = None
        for i in range(death_line_index - 1, -1, -1):
            if "[Login][Hours Survived:" in player_lines[i]:
                login_line_index = i
                break

        if login_line_index is None:
            print("No login found before death")
            return None, None

        # Get skills from the line after login (current skills at login time)
        pre_death_skills = {}
        if login_line_index + 1 < len(player_lines):
            next_line = player_lines[login_line_index + 1]
            if "Hours Survived:" in next_line and "=" in next_line:
                pre_death_skills = self.parse_skill_line(next_line)

        # Apply any level changes between login and death
        for i in range(login_line_index + 2, death_line_index):
            line = player_lines[i]
            if "[Level Changed]" in line:
                match = re.search(r"\[Level Changed\]\[([^\]]+)\]\[(\d+)\]", line)
                if match:
                    skill_name = match.group(1)
                    new_level = int(match.group(2))
                    pre_death_skills[skill_name] = new_level

        # Find current skills (after "Created Player" line)
        current_skills = {}
        for i, line in enumerate(player_lines):
            if "[Created Player" in line and i + 1 < len(player_lines):
                next_line = player_lines[i + 1]
                if "Hours Survived: 0" in next_line and "=" in next_line:
                    current_skills = self.parse_skill_line(next_line)
                    break

        return pre_death_skills, current_skills

    async def verify_player_online(self, log_line: str) -> bool | None:
        """Monitor the log to verify player is online."""
        if "Players connected" in log_line:
            print("Players command received!")
            self.players_command_received = True
            return None

        if self.players_command_received:
            if len(log_line) == 0:
                print("No players or end of list.")
                return False
            if log_line.startswith("-"):
                if f"{self.player_name}" in log_line:
                    print("Player found online!")
                    return True
                return None
            print("Unexpected log line.")
            return False

    async def verify_addxp_commands(self, log_line: str) -> bool | None:
        """Verify addxp commands were executed successfully."""
        if "Added" in log_line and f"xp's to {self.player_name}" in log_line:
            self.addxp_commands_confirmed += 1
            print(
                f"AddXP command confirmed ({self.addxp_commands_confirmed}/{self.addxp_commands_sent})"
            )

            if self.addxp_commands_confirmed >= self.addxp_commands_sent:
                print("All addXP commands confirmed!")
                return True

        return None

    async def log_watcher(
        self,
        log_handler: Callable[[str], Coroutine[None, None, bool | None]],
        timeout: int = 10,
    ):
        """Watches log lines with tail and runs a callback on each line."""
        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-fn 1",
                self.log_file_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if process.stdout is None:
                print("Failed to access log")
                return False

            print(f"Tailing log file: {self.log_file_path}")
            start_time = time.time()
            async for line in process.stdout:
                decoded_line = line.decode("utf-8").strip()
                print(decoded_line)  # log line
                result = await log_handler(decoded_line)
                if result is None:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > timeout:
                        print(f"Watcher timed out after {timeout} seconds")
                        return False
                    continue
                if result:
                    return True

                print("Log handler failed")
                return False

            return False
        except asyncio.CancelledError:
            print(f"Task cancelled for: {self.log_file_path}")
            return False
        finally:
            if process:
                try:
                    process.terminate()
                    await process.wait()
                    print("Terminated log watcher process.")
                except ProcessLookupError:
                    print("ProcessLookupError occurred, process already stopped?")

    async def restore_levels(self) -> bool:
        """Main method to restore player levels."""
        # Check if player has admin privileges
        # player_row = await get_player(SYSTEM_USERS[self.server_name], self.player_name)
        # if player_row and player_row[13]:
        #     print("Player has admin privileges, skipping restore.")
        #     return False

        # Verify player is online
        check_if_online = asyncio.create_task(
            self.log_watcher(self.verify_player_online, timeout=5)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        is_online = await check_if_online
        if not is_online:
            print("Player is not online")
            return False

        # Analyze death and get skill differences
        pre_death_skills, current_skills = self.analyze_player_death()

        if not pre_death_skills or not current_skills:
            print("Could not determine skill levels")
            return False

        print(f"Pre-death skills: {pre_death_skills}")
        print(f"Current skills: {current_skills}")

        # Calculate XP differences needed
        xp_commands = []
        for skill, pre_level in pre_death_skills.items():
            current_level = current_skills.get(skill, 0)
            if pre_level > current_level:
                current_xp = self.get_xp_for_level(skill, current_level)
                target_xp = self.get_xp_for_level(skill, pre_level)
                xp_needed = target_xp - current_xp
                if xp_needed > 0:
                    xp_commands.append(
                        f'addxp "{self.player_name}" {skill}={xp_needed}'
                    )

        if not xp_commands:
            print("No XP restoration needed")
            return True

        print(f"Will execute {len(xp_commands)} addXP commands")
        self.addxp_commands_sent = len(xp_commands)
        self.addxp_commands_confirmed = 0

        # Start watching for command confirmations
        check_commands = asyncio.create_task(
            self.log_watcher(self.verify_addxp_commands, timeout=30)
        )

        # Send all addXP commands
        for cmd in xp_commands:
            print(f"Sending command: {cmd}")
            await pz_send_command(SYSTEM_USERS[self.server_name], cmd)
            await asyncio.sleep(0.1)  # Small delay between commands

        # Wait for all commands to be confirmed
        commands_successful = await check_commands

        return commands_successful
