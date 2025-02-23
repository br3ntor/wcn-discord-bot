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
