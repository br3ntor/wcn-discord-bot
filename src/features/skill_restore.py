import asyncio
import glob
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.config import Config
from src.services.pz_server import pz_add_xp

logger = logging.getLogger(__name__)

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
        self.perk_log_path = f"/home/{SYSTEM_USERS[server_name]}/Zomboid/Logs"

    def get_perk_logs(self, days_back: int = 3) -> list[str]:
        """Find all PerkLog files within the specified number of days, including archived folders."""
        cutoff_time = datetime.now().timestamp() - (days_back * 24 * 3600)
        
        perk_files = []
        
        root_pattern = f"{self.perk_log_path}/*PerkLog.txt"
        perk_files.extend(glob.glob(root_pattern))
        
        folder_pattern = f"{self.perk_log_path}/logs_*/*PerkLog.txt"
        perk_files.extend(glob.glob(folder_pattern))
        
        valid_files = [
            f for f in perk_files 
            if os.path.getmtime(f) >= cutoff_time
        ]
        
        valid_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        logger.debug(f"Found {len(valid_files)} PerkLog files within {days_back} days")
        for f in valid_files:
            logger.debug(f"  - {f} (mtime: {datetime.fromtimestamp(os.path.getmtime(f))})")
        
        return valid_files

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
            logger.debug("No timestamp found in reference line")
            return {}

        logger.debug(f"Reference timestamp: {ref_timestamp}")
        logger.debug(f"Reference line: {lines[reference_index][:80]}...")

        for offset in range(1, min(search_range + 1, len(lines) - reference_index)):
            candidate = lines[reference_index + offset]
            if self.is_skill_line(candidate):
                candidate_ts = self.extract_timestamp(candidate)
                if candidate_ts and self.timestamps_close(
                    ref_timestamp, candidate_ts, 1.0
                ):
                    time_diff = abs(candidate_ts - ref_timestamp)
                    logger.debug(
                        f"Found skills at +{offset} lines, time diff: {time_diff:.3f}s"
                    )
                    logger.debug(
                        f"Reference: {ref_timestamp}, Candidate: {candidate_ts}"
                    )
                    logger.debug(f"Candidate line: {candidate[:80]}...")
                    return self.parse_skill_line(candidate)

        for offset in range(1, min(search_range + 1, reference_index + 1)):
            candidate = lines[reference_index - offset]
            if self.is_skill_line(candidate):
                candidate_ts = self.extract_timestamp(candidate)
                if candidate_ts and self.timestamps_close(
                    ref_timestamp, candidate_ts, 1.0
                ):
                    time_diff = abs(candidate_ts - ref_timestamp)
                    logger.debug(
                        f"Found skills at -{offset} lines, time diff: {time_diff:.3f}s"
                    )
                    logger.debug(
                        f"Reference: {ref_timestamp}, Candidate: {candidate_ts}"
                    )
                    logger.debug(f"Candidate line: {candidate[:80]}...")
                    return self.parse_skill_line(candidate)

        logger.debug("No skill lines found within 1.0s proximity")
        return {}

    def get_xp_for_level(self, skill: str, level: int) -> int:
        """Get the total XP needed to reach a specific level."""
        if skill in PASSIVE_SKILLS:
            return sum(PASSIVE_SKILL_XP[1 : level + 1]) if level > 0 else 0
        else:
            return sum(REGULAR_SKILL_XP[1 : level + 1]) if level > 0 else 0

    def extract_player_data_from_file(self, file_path: str) -> Optional[list[str]]:
        """Extract all log lines for the player from a single PerkLog file."""
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Error reading PerkLog file {file_path}: {e}")
            return None
        
        player_lines = [
            line.strip() for line in lines if f"][{self.player_name}][" in line
        ]
        
        if not player_lines:
            return None
            
        return player_lines

    def find_deaths_in_file(self, player_lines: list[str]) -> list[tuple[int, int]]:
        """Find all deaths in player lines, returns list of (line_index, hours_survived)."""
        deaths = []
        for i, line in enumerate(player_lines):
            if "[Died][Hours Survived:" in line:
                match = re.search(r"\[Died\]\[Hours Survived: (\d+)\]", line)
                if match:
                    deaths.append((i, int(match.group(1))))
        return deaths

    def find_most_significant_death_and_skills(
        self, player_lines: list[str], death_line_index: int
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Find pre-death and current skills for a given death index."""
        login_line_index = None
        for i in range(death_line_index - 1, -1, -1):
            if "[Login][Hours Survived:" in player_lines[i]:
                login_line_index = i
                break

        if login_line_index is None:
            logger.warning("No login found before death")
            return {}, {}

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
                skills = self.find_skills_by_proximity(player_lines, i)
                if skills:
                    current_skills = skills
                    break

        return pre_death_skills, current_skills

    def analyze_player_death(
        self,
    ) -> Tuple[Optional[Dict[str, int]], Optional[Dict[str, int]]]:
        """
        Analyze player's most significant death across multiple PerkLog files.
        Searches through all PerkLog files within the last 3 days (including archived folders).
        Returns pre-death and current skill levels from the death with longest survival time.
        """
        perk_log_files = self.get_perk_logs(days_back=3)
        
        if not perk_log_files:
            logger.warning("No PerkLog files found within search range")
            return None, None

        logger.info(f"Searching through {len(perk_log_files)} PerkLog files")

        best_death = None
        best_death_hours = -1
        best_file_path = None
        best_player_lines = None
        best_death_line_index = None

        for file_path in perk_log_files:
            player_lines = self.extract_player_data_from_file(file_path)
            if not player_lines:
                continue
                
            deaths = self.find_deaths_in_file(player_lines)
            if not deaths:
                continue
                
            most_sig_death = max(deaths, key=lambda x: x[1])
            death_idx, death_hours = most_sig_death
            
            logger.debug(f"File {os.path.basename(file_path)}: found death at {death_hours} hours")
            
            if death_hours > best_death_hours:
                best_death_hours = death_hours
                best_death = most_sig_death
                best_file_path = file_path
                best_player_lines = player_lines
                best_death_line_index = death_idx

        if best_death is None or best_player_lines is None or best_file_path is None or best_death_line_index is None:
            logger.warning("No death records found for player in any PerkLog file")
            return None, None

        logger.info(f"Most significant death found: {best_death_hours} hours survived in {os.path.basename(best_file_path)}")

        pre_death_skills, current_skills = self.find_most_significant_death_and_skills(
            best_player_lines, best_death_line_index
        )

        return pre_death_skills, current_skills

    async def restore_levels(self) -> bool:
        """Main method to restore player levels."""
        pre_death_skills, current_skills = self.analyze_player_death()

        if not pre_death_skills or not current_skills:
            logger.warning("Could not determine skill levels")
            return False

        logger.info(f"Pre-death skills: {pre_death_skills}")
        logger.info(f"Current skills: {current_skills}")

        xp_commands: list[tuple[str, int]] = []
        for skill, pre_level in pre_death_skills.items():
            current_level = current_skills.get(skill, 0)
            if pre_level > current_level:
                current_xp = self.get_xp_for_level(skill, current_level)
                target_xp = self.get_xp_for_level(skill, pre_level)
                xp_needed = target_xp - current_xp
                if xp_needed > 0:
                    xp_commands.append((skill, xp_needed))

        if not xp_commands:
            logger.info("No XP restoration needed")
            return True

        logger.info(f"Will execute {len(xp_commands)} addXP commands")

        for skill, xp_needed in xp_commands:
            logger.debug(
                'Sending command: addxp "%s" %s=%s',
                self.player_name,
                skill,
                xp_needed,
            )
            success, response = await pz_add_xp(
                SYSTEM_USERS[self.server_name], self.player_name, skill, xp_needed
            )
            await asyncio.sleep(0.2)
            if not success:
                logger.warning(
                    "Failed to restore %s XP for %s: %s",
                    skill,
                    self.player_name,
                    response,
                )
                return False

        return True
