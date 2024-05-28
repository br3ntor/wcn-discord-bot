import asyncio


async def server_isrunning(server: str) -> bool:
    """Check if the given zomboid server name is running"""

    # Maybe can validate user exists here?

    cmd = [
        "runuser",
        f"{server}",
        "-c",
        f"ps -f -u {server} | grep ProjectZomboid64 | grep -v grep",
    ]

    try:
        # Running this script here takes a certain amount of time I wonder if
        # another method, like looking up process list and start commands is better/faster?
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

        # I don't think this is needed but doesn't hurt either
        await process.wait()
    except asyncio.SubprocessError as e:
        print(f"Subprocess error occurred: {e}")

    out, err = output.decode(), error.decode()

    print(f"Server is running:\n{out}" if out else "Server is off, no command output")
    print(err)
    return bool(out)
