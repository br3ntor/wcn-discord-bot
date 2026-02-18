import asyncio
import glob
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Callable, Coroutine, Dict, Optional, Tuple

from src.config import Config
from src.services.game_db import get_player
from src.services.pz_server import pz_send_command

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS

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
        return max(
            perk_files, key=lambda x: datetime.fromtimestamp(os.path.getmtime(x))
        )

    def extract_timestamp(self, line: str) -> Optional[float]:
        """Extract timestamp from a log line and return as float seconds."""
        match = re.search(r"\[\d{2}-\d{2}-\d{2} (\d{2}):(\d{2}):(\d{2}\.\d{3})\]", line)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
        return None

    def timestamps_close(
        self, ts1: Optional[float], ts2: Optional[float], threshold: float = 1.0
    ) -> bool:
        """Check if two timestamps are within threshold seconds of each other."""
        if ts1 is None or ts2 is None:
            return False
        return abs(ts1 - ts2) <= threshold

    def parse_skill_line(self, line: str) -> Dict[str, int]:
        """Parse a skill line and return a dictionary of skill levels."""
        skills = {}
        match = re.search(r"\[([^\]]*)\]\[Hours Survived:", line)
        if match:
            skill_data = match.group(1)
            for skill_pair in skill_data.split(", "):
                if "=" in skill_pair:
                    skill, level = skill_pair.split("=")
                    skills[skill.strip()] = int(level.strip())
        return skills

    def is_skill_line(self, line: str) -> bool:
        """Check if a line contains skill data (has skill=level pattern and Hours Survived)."""
        return (
            "=" in line
            and "Hours Survived:" in line
            and not any(
                keyword in line
                for keyword in [
                    "[Login]",
                    "[Died]",
                    "[Created Player",
                    "[Level Changed]",
                ]
            )
        )

    def find_skills_by_proximity(
        self, lines: list, reference_index: int, search_range: int = 3
    ) -> Dict[str, int]:
        """Find skill line closest to a reference event using time proximity."""
        if reference_index < 0 or reference_index >= len(lines):
            return {}

        ref_timestamp = self.extract_timestamp(lines[reference_index])
        if ref_timestamp is None:
            print("DEBUG: No timestamp found in reference line")
            return {}

        print(f"DEBUG: Reference timestamp: {ref_timestamp}")
        print(f"DEBUG: Reference line: {lines[reference_index][:80]}...")

        for offset in range(1, min(search_range + 1, len(lines) - reference_index)):
            candidate = lines[reference_index + offset]
            if self.is_skill_line(candidate):
                candidate_ts = self.extract_timestamp(candidate)
                if candidate_ts and self.timestamps_close(
                    ref_timestamp, candidate_ts, 1.0
                ):
                    time_diff = abs(candidate_ts - ref_timestamp)
                    print(
                        f"DEBUG: Found skills at +{offset} lines, time diff: {time_diff:.3f}s"
                    )
                    print(
                        f"DEBUG: Reference: {ref_timestamp}, Candidate: {candidate_ts}"
                    )
                    print(f"DEBUG: Candidate line: {candidate[:80]}...")
                    return self.parse_skill_line(candidate)

        for offset in range(1, min(search_range + 1, reference_index + 1)):
            candidate = lines[reference_index - offset]
            if self.is_skill_line(candidate):
                candidate_ts = self.extract_timestamp(candidate)
                if candidate_ts and self.timestamps_close(
                    ref_timestamp, candidate_ts, 1.0
                ):
                    time_diff = abs(candidate_ts - ref_timestamp)
                    print(
                        f"DEBUG: Found skills at -{offset} lines, time diff: {time_diff:.3f}s"
                    )
                    print(
                        f"DEBUG: Reference: {ref_timestamp}, Candidate: {candidate_ts}"
                    )
                    print(f"DEBUG: Candidate line: {candidate[:80]}...")
                    return self.parse_skill_line(candidate)

        print("DEBUG: No skill lines found within 1.0s proximity")
        return {}

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
        Uses time proximity matching for both B41 and B42 log patterns.
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

        player_lines = [
            line.strip() for line in lines if f"][{self.player_name}][" in line
        ]

        if not player_lines:
            print(f"No log entries found for player {self.player_name}")
            return None, None

        deaths = []
        for i, line in enumerate(player_lines):
            if "[Died][Hours Survived:" in line:
                match = re.search(r"\[Died\]\[Hours Survived: (\d+)\]", line)
                if match:
                    deaths.append((i, int(match.group(1))))

        if not deaths:
            print("No death records found")
            return None, None

        most_significant_death = max(deaths, key=lambda x: x[1])
        death_line_index, death_hours = most_significant_death

        print(f"Most significant death at {death_hours} hours survived")

        login_line_index = None
        for i in range(death_line_index - 1, -1, -1):
            if "[Login][Hours Survived:" in player_lines[i]:
                login_line_index = i
                break

        if login_line_index is None:
            print("No login found before death")
            return None, None

        pre_death_skills = self.find_skills_by_proximity(player_lines, login_line_index)

        if pre_death_skills:
            for i in range(login_line_index + 1, death_line_index):
                line = player_lines[i]
                if "[Level Changed]" in line:
                    match = re.search(r"\[Level Changed\]\[([^\]]+)\]\[(\d+)\]", line)
                    if match:
                        skill_name = match.group(1)
                        new_level = int(match.group(2))
                        pre_death_skills[skill_name] = new_level

        current_skills = {}
        for i in range(death_line_index + 1, len(player_lines)):
            line = player_lines[i]
            if "[Login][Hours Survived:" in line or "[Created Player" in line:
                print(
                    f"DEBUG: Found {'Login' if '[Login' in line else 'Created Player'} at index {i}"
                )
                skills = self.find_skills_by_proximity(player_lines, i)
                if skills:
                    current_skills = skills
                    print(f"DEBUG: Successfully found {len(skills)} current skills")
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
        process = None
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
                print(decoded_line)
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
        check_if_online = asyncio.create_task(
            self.log_watcher(self.verify_player_online, timeout=10)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        is_online = await check_if_online
        if not is_online:
            print("Player is not online")
            return False

        pre_death_skills, current_skills = self.analyze_player_death()

        if not pre_death_skills or not current_skills:
            print("Could not determine skill levels")
            return False

        print(f"Pre-death skills: {pre_death_skills}")
        print(f"Current skills: {current_skills}")

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

        check_commands = asyncio.create_task(
            self.log_watcher(self.verify_addxp_commands, timeout=60)
        )

        for cmd in xp_commands:
            print(f"Sending command: {cmd}")
            await pz_send_command(SYSTEM_USERS[self.server_name], cmd)
            await asyncio.sleep(0.1)

        commands_successful = await check_commands

        return commands_successful
