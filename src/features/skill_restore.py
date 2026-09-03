import asyncio
import glob
import logging
import os
import re
from datetime import datetime
from typing import Optional

from src.config import Config
from src.services.pz_server import pz_add_xp

logger = logging.getLogger(__name__)

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS

DEFAULT_DAYS_BACK = 7

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

LOGIN_RE = re.compile(r"\[Login\]\[Hours Survived: (\d+)\]")
DIED_RE = re.compile(r"\[Died\]\[Hours Survived: (\d+)\]")
CREATED_RE = re.compile(r"\[Created Player (\d+)\]")
LEVEL_CHANGED_RE = re.compile(r"\[Level Changed\]\[([^\]]+)\]\[(\d+)\]")

# A wiped character appears as a session start whose Hours Survived regressed
# far below the player's peak, without a [Died] record in between.
WIPE_REGRESSION_FACTOR = 0.5
WIPE_MIN_PEAK_HOURS = 20

# Failure reasons returned by restore_levels.
REASON_OK = "ok"
REASON_NO_CHANGE = "no_change"
REASON_NO_DATA = "no_data"
REASON_NO_RECORD = "no_record"
REASON_NO_RELOGIN = "no_relogin"
REASON_NO_SNAPSHOT = "no_snapshot"
REASON_RCON = "rcon"

FAILURE_EXPLANATIONS = {
    REASON_NO_DATA: "No PerkLog records were found for this player in the "
    f"last {DEFAULT_DAYS_BACK} days.",
    REASON_NO_RECORD: "No death or wiped-character record was found in the "
    f"last {DEFAULT_DAYS_BACK} days.",
    REASON_NO_RELOGIN: "The player has not logged in since the recorded "
    "death, so current skill levels are unknown.",
    REASON_NO_SNAPSHOT: "A death or wipe was found, but the surrounding "
    "skill records could not be parsed.",
    REASON_RCON: "The server rejected or could not execute the addXP commands.",
}


class LevelRestore:
    """
    Restores a player's skill levels to what they were before their most
    significant death, or before their character was wiped when no death was
    logged.
    """

    def __init__(
        self,
        server_name: str,
        player_name: str,
        perk_log_path: Optional[str] = None,
    ) -> None:
        self.server_name = server_name
        self.player_name = player_name
        self.log_prefix = f"[{server_name}/{player_name}]"
        if perk_log_path is None:
            perk_log_path = f"/home/{SYSTEM_USERS[server_name]}/Zomboid/Logs"
        self.perk_log_path = perk_log_path

    def get_perk_logs(self, days_back: int = DEFAULT_DAYS_BACK) -> list[str]:
        """Find all PerkLog files within the specified number of days, including archived folders.

        Files are returned oldest first so they can be concatenated into a
        chronological timeline.
        """
        cutoff_time = datetime.now().timestamp() - (days_back * 24 * 3600)

        perk_files = []
        perk_files.extend(glob.glob(f"{self.perk_log_path}/*PerkLog.txt"))
        perk_files.extend(glob.glob(f"{self.perk_log_path}/logs_*/*PerkLog.txt"))

        valid_files = [f for f in perk_files if os.path.getmtime(f) >= cutoff_time]

        valid_files.sort(key=os.path.getmtime)

        logger.debug(
            "%s Found %d PerkLog files within %d days",
            self.log_prefix,
            len(valid_files),
            days_back,
        )
        for f in valid_files:
            logger.debug(
                "%s   - %s (mtime: %s)",
                self.log_prefix,
                f,
                datetime.fromtimestamp(os.path.getmtime(f)),
            )

        return valid_files

    def extract_player_timeline(self) -> list[str]:
        """Extract the player's log lines from every PerkLog file in the search window.

        Files are visited oldest first, so the returned lines form a single
        chronological timeline spanning log rotations and server restarts.
        """
        timeline: list[str] = []
        for file_path in self.get_perk_logs():
            player_lines = self.extract_player_data_from_file(file_path)
            if player_lines:
                timeline.extend(player_lines)
        return timeline

    def extract_player_data_from_file(self, file_path: str) -> Optional[list[str]]:
        """Extract all log lines for the player from a single PerkLog file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(
                "%s Error reading PerkLog file %s: %s",
                self.log_prefix,
                file_path,
                e,
            )
            return None

        player_lines = [
            line.strip() for line in lines if f"][{self.player_name}][" in line
        ]

        if not player_lines:
            return None

        logger.debug(
            "%s %s: %d player lines",
            self.log_prefix,
            os.path.basename(file_path),
            len(player_lines),
        )
        return player_lines

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

    def parse_skill_line(self, line: str) -> dict[str, int]:
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
        self, lines: list[str], reference_index: int, search_range: int = 3
    ) -> dict[str, int]:
        """Find skill line closest to a reference event using time proximity."""
        if reference_index < 0 or reference_index >= len(lines):
            return {}

        ref_timestamp = self.extract_timestamp(lines[reference_index])
        if ref_timestamp is None:
            logger.debug("%s No timestamp found in reference line", self.log_prefix)
            return {}

        logger.debug("%s Reference timestamp: %s", self.log_prefix, ref_timestamp)
        logger.debug(
            "%s Reference line: %s...",
            self.log_prefix,
            lines[reference_index][:80],
        )

        for offset in range(1, min(search_range + 1, len(lines) - reference_index)):
            candidate = lines[reference_index + offset]
            if self.is_skill_line(candidate):
                candidate_ts = self.extract_timestamp(candidate)
                if candidate_ts and self.timestamps_close(
                    ref_timestamp, candidate_ts, 1.0
                ):
                    time_diff = abs(candidate_ts - ref_timestamp)
                    logger.debug(
                        "%s Found skills at +%d lines, time diff: %.3fs",
                        self.log_prefix,
                        offset,
                        time_diff,
                    )
                    logger.debug(
                        "%s Candidate line: %s...",
                        self.log_prefix,
                        candidate[:80],
                    )
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
                        "%s Found skills at -%d lines, time diff: %.3fs",
                        self.log_prefix,
                        offset,
                        time_diff,
                    )
                    logger.debug(
                        "%s Candidate line: %s...",
                        self.log_prefix,
                        candidate[:80],
                    )
                    return self.parse_skill_line(candidate)

        logger.debug("%s No skill lines found within 1.0s proximity", self.log_prefix)
        return {}

    def session_start_hours(self, line: str) -> Optional[int]:
        """Return Hours Survived for a session start line (login or created player)."""
        match = LOGIN_RE.search(line)
        if match:
            return int(match.group(1))
        if CREATED_RE.search(line):
            # Created Player lines are always fresh characters at 0 hours.
            return 0
        return None

    def find_session_starts(self, lines: list[str]) -> list[int]:
        """Find indexes of all session start lines (logins and created players)."""
        return [
            i
            for i, line in enumerate(lines)
            if LOGIN_RE.search(line) or CREATED_RE.search(line)
        ]

    def find_deaths(self, lines: list[str]) -> list[tuple[int, int]]:
        """Find all deaths in the player timeline, returns list of (line_index, hours_survived)."""
        deaths = []
        for i, line in enumerate(lines):
            match = DIED_RE.search(line)
            if match:
                deaths.append((i, int(match.group(1))))
        return deaths

    def apply_level_changes(
        self, skills: dict[str, int], lines: list[str], start_idx: int, end_idx: int
    ) -> dict[str, int]:
        """Apply [Level Changed] updates in lines[start_idx:end_idx] to the skill dict."""
        for line in lines[start_idx:end_idx]:
            match = LEVEL_CHANGED_RE.search(line)
            if match:
                skills[match.group(1)] = int(match.group(2))
        return skills

    def find_latest_session_skills(
        self, lines: list[str], starts: list[int], min_index: int
    ) -> dict[str, int]:
        """Find skills for the latest session start at or after min_index.

        Falls back to earlier session starts when the latest one has no
        adjacent skill snapshot. [Level Changed] events are applied up to the
        next session start so the result reflects the player's most recent
        known state.
        """
        for anchor in reversed([i for i in starts if i >= min_index]):
            skills = self.find_skills_by_proximity(lines, anchor)
            if skills:
                later = [i for i in starts if i > anchor]
                end = later[0] if later else len(lines)
                return self.apply_level_changes(skills, lines, anchor + 1, end)
        return {}

    def find_skills_for_death(
        self, lines: list[str], death_line_index: int
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Find pre-death and current skills for a death at the given index.

        The timeline spans every PerkLog file in the search window, so the
        session that ended in the death and the first session after it may
        live in different files (e.g. after a log rotation or restart).
        """
        starts = self.find_session_starts(lines)

        pre_death_skills: dict[str, int] = {}
        previous_starts = [i for i in starts if i < death_line_index]
        if previous_starts:
            anchor = previous_starts[-1]
            pre_death_skills = self.find_skills_by_proximity(lines, anchor)
            if pre_death_skills:
                pre_death_skills = self.apply_level_changes(
                    pre_death_skills, lines, anchor + 1, death_line_index
                )

        current_skills = self.find_latest_session_skills(
            lines, starts, death_line_index + 1
        )

        return pre_death_skills, current_skills

    def find_wipe_boundary(self, lines: list[str]) -> Optional[tuple[int, int, int]]:
        """Locate the most significant character reset without a [Died] record.

        A session start (login or created player) whose Hours Survived
        regressed below WIPE_REGRESSION_FACTOR of the running peak is a reset
        candidate. Candidates explained by a death between the previous
        session start and the reset (a normal new character after death) are
        ignored, as are characters that never reached WIPE_MIN_PEAK_HOURS.
        Returns (anchor_index, boundary_index, wiped_peak_hours) where the
        anchor is the last session start of the lost character, or None when
        no wipe can be identified.
        """
        starts = self.find_session_starts(lines)
        if len(starts) < 2:
            return None

        hours: dict[int, int] = {}
        for i in starts:
            h = self.session_start_hours(lines[i])
            if h is not None:
                hours[i] = h

        deaths = [d for d, _ in self.find_deaths(lines)]

        best: Optional[tuple[int, int, int]] = None
        running_peak = 0
        for pos, idx in enumerate(starts):
            h = hours[idx]
            if h >= running_peak:
                running_peak = h
                continue
            if h >= running_peak * WIPE_REGRESSION_FACTOR:
                continue
            anchor = starts[pos - 1]
            if any(anchor < d < idx for d in deaths):
                continue
            last_death = max((d for d in deaths if d < anchor), default=-1)
            wiped_peak = max(hours[j] for j in starts if last_death < j < idx)
            if wiped_peak < WIPE_MIN_PEAK_HOURS:
                continue
            if best is None or wiped_peak > best[2]:
                best = (anchor, idx, wiped_peak)
        return best

    def get_xp_for_level(self, skill: str, level: int) -> int:
        """Get the total XP needed to reach a specific level."""
        if skill in PASSIVE_SKILLS:
            return sum(PASSIVE_SKILL_XP[1 : level + 1]) if level > 0 else 0
        else:
            return sum(REGULAR_SKILL_XP[1 : level + 1]) if level > 0 else 0

    def compute_xp_commands(
        self, pre_death_skills: dict[str, int], current_skills: dict[str, int]
    ) -> list[tuple[str, int]]:
        """Build the addXP (skill, amount) command list restoring pre-death levels."""
        xp_commands: list[tuple[str, int]] = []
        for skill, pre_level in pre_death_skills.items():
            current_level = current_skills.get(skill, 0)
            if pre_level > current_level:
                current_xp = self.get_xp_for_level(skill, current_level)
                target_xp = self.get_xp_for_level(skill, pre_level)
                xp_needed = target_xp - current_xp
                if xp_needed > 0:
                    xp_commands.append((skill, xp_needed))
        return xp_commands

    def analyze_player_history(
        self,
    ) -> tuple[dict[str, int], dict[str, int], str]:
        """
        Analyze the player's PerkLog timeline across all files in the search
        window and return (pre_loss_skills, current_skills, reason).

        The most significant loss is restored: the death with the longest
        Hours Survived, or a wiped character (no [Died] record) whose peak
        Hours Survived exceeds every death. reason is REASON_OK on success or
        one of the REASON_* failure codes.
        """
        lines = self.extract_player_timeline()
        if not lines:
            logger.warning("%s No PerkLog records found for player", self.log_prefix)
            return {}, {}, REASON_NO_DATA

        deaths = self.find_deaths(lines)
        death_hours = max((h for _, h in deaths), default=-1)
        boundary = self.find_wipe_boundary(lines)

        if boundary is not None and boundary[2] > death_hours:
            anchor_idx, boundary_idx, wiped_peak = boundary
            logger.info(
                "%s Wiped character detected without a [Died] record "
                "(peak %d hours survived)",
                self.log_prefix,
                wiped_peak,
            )

            pre_death_skills = self.find_skills_by_proximity(lines, anchor_idx)
            if pre_death_skills:
                pre_death_skills = self.apply_level_changes(
                    pre_death_skills, lines, anchor_idx + 1, boundary_idx
                )
            if not pre_death_skills:
                logger.warning(
                    "%s Wipe found but no pre-wipe skill snapshot parsed",
                    self.log_prefix,
                )
                return {}, {}, REASON_NO_SNAPSHOT

            starts = self.find_session_starts(lines)
            current_skills = self.find_latest_session_skills(
                lines, starts, boundary_idx
            )
            if not current_skills:
                logger.warning(
                    "%s Wipe found but no current skill snapshot parsed",
                    self.log_prefix,
                )
                return {}, {}, REASON_NO_SNAPSHOT

            return pre_death_skills, current_skills, REASON_OK

        if deaths:
            death_idx, _ = max(deaths, key=lambda x: x[1])
            logger.info(
                "%s Most significant death: %d hours survived",
                self.log_prefix,
                death_hours,
            )
            pre_death_skills, current_skills = self.find_skills_for_death(
                lines, death_idx
            )
            if not current_skills:
                starts_after = [
                    i for i in self.find_session_starts(lines) if i > death_idx
                ]
                if not starts_after:
                    logger.warning(
                        "%s Death found but the player has not logged in since",
                        self.log_prefix,
                    )
                    return {}, {}, REASON_NO_RELOGIN
                logger.warning(
                    "%s Post-death session found but no skill snapshot parsed",
                    self.log_prefix,
                )
                return {}, {}, REASON_NO_SNAPSHOT
            if not pre_death_skills:
                logger.warning(
                    "%s Death found but no pre-death skill snapshot parsed",
                    self.log_prefix,
                )
                return {}, {}, REASON_NO_SNAPSHOT
            return pre_death_skills, current_skills, REASON_OK

        logger.warning(
            "%s No death or wiped-character record found in PerkLogs",
            self.log_prefix,
        )
        return {}, {}, REASON_NO_RECORD

    async def restore_levels(self) -> tuple[bool, str]:
        """Main method to restore player levels.

        Returns (success, reason) where reason is one of the REASON_* codes
        so callers can report a specific failure to the user.
        """
        pre_death_skills, current_skills, reason = self.analyze_player_history()
        if reason != REASON_OK:
            return False, reason

        logger.info("%s Pre-loss skills: %s", self.log_prefix, pre_death_skills)
        logger.info("%s Current skills: %s", self.log_prefix, current_skills)

        xp_commands = self.compute_xp_commands(pre_death_skills, current_skills)

        if not xp_commands:
            logger.info("%s No XP restoration needed", self.log_prefix)
            return True, REASON_NO_CHANGE

        logger.info(
            "%s Will execute %d addXP commands", self.log_prefix, len(xp_commands)
        )

        for skill, xp_needed in xp_commands:
            logger.debug(
                '%s Sending command: addxp "%s" %s=%s',
                self.log_prefix,
                self.player_name,
                skill,
                xp_needed,
            )
            success, response = await pz_add_xp(
                SYSTEM_USERS[self.server_name], self.player_name, skill, xp_needed
            )
            if not success:
                logger.warning(
                    "%s Failed to restore %s XP: %s",
                    self.log_prefix,
                    skill,
                    response,
                )
                return False, REASON_RCON
            await asyncio.sleep(0.2)

        logger.info(
            "%s Successfully executed %d addXP commands",
            self.log_prefix,
            len(xp_commands),
        )
        return True, REASON_OK
