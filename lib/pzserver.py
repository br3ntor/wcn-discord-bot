import asyncio
import re


async def pz_send_command(system_user: str, server_command: str):
    cmd = [
        "sudo",
        "-u",
        system_user,
        f"/home/{system_user}/pzserver",
        "send",
        f"{server_command}",
    ]

    try:
        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        # Get the output of the subprocess
        output, error = await process.communicate()

        if process.returncode != 0:
            print(f"Error: {error.decode().strip()}")
            return False
        else:
            print(f"Output: {output.decode().strip()}")
            return True

    except Exception as e:
        print(f"Subprocess error occurred: {e}")
        return False


async def pz_send_message(server: str, message: str) -> bool:
    valid_msg = re.sub(r"[^a-zA-Z!?\s\d]", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    return await pz_send_command(server, server_msg)