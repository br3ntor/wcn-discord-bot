import secrets
import string
from datetime import datetime


def get_last_14th() -> datetime:
    """Get the date of the most recent 14th (either current month or previous month)."""
    today = datetime.now()

    # If we're before the 14th of current month, get previous month's 14th
    if today.day < 14:
        # If we're in January, go back to December
        if today.month == 1:
            return datetime(today.year - 1, 12, 14)
        else:
            return datetime(today.year, today.month - 1, 14)
    # If we're after the 14th, use current month's 14th
    else:
        return datetime(today.year, today.month, 14)


def get_last_occurrence_of_day(day_number: int) -> datetime:
    """
    Get the date of the most recent occurrence of a specific day of the month.

    Args:
        day_number: The day of the month (e.g., 14 for the 14th) you want to find.

    Returns:
        A datetime object representing the most recent occurrence of that day.
    """
    if not 1 <= day_number <= 31:
        raise ValueError("day_number must be between 1 and 31.")

    today = datetime.now()

    # If today's day is before the specified day_number, get the day from the previous month
    if today.day < day_number:
        # If it's January, go back to December of the previous year
        if today.month == 1:
            return datetime(today.year - 1, 12, day_number)
        else:
            return datetime(today.year, today.month - 1, day_number)
    # Otherwise, use the specified day from the current month
    else:
        return datetime(today.year, today.month, day_number)


def show_donation_progress(current_amount, goal_amount):
    """Prints a nice progress meter."""
    # Calculate percentage (rounded to 1 decimal place)
    percentage = (current_amount / goal_amount) * 100
    percentage = round(percentage, 1)

    # Create progress bar (20 characters long)
    bar_length = 20
    filled_length = int(bar_length * min(percentage, 100) / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # Build the message string with newline separators
    message = f"Donation Progress: [{bar}] {percentage}%\n"
    message += f"We are {percentage}% towards our goal of ${goal_amount}!\n"
    message += f"Current amount raised: ${current_amount:.2f}"

    # Add special message when goal is met or exceeded
    if percentage == 100:
        message += "\n🎉 Congratulations! We've met our donation goal! 🎉"
    elif percentage > 100:
        message += "\n🎉 Congratulations! We've met and exceeded our donation goal! 🎉"

    return message


def generate_pz_password(length: int = 12) -> str:
    """Generates a random alphanumeric password without symbols."""
    # Define the characters: abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
    alphabet = string.ascii_letters + string.digits

    # Generate a random string by picking characters from the alphabet
    password = "".join(secrets.choice(alphabet) for _ in range(length))

    return password
