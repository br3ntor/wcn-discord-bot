## WCN Project Zomboid Discord Bot

This bot can control one or more Project Zomboid servers running on a single machine that were installed with LinuxGSM.

### TODO

- Model rest of the commands after basic flow in send_message, namely we are defering properly and checking is server is runnning
  before sending any commands.
- Fix other non consistent patterns in the code base, system_user vs server_username, stuff like that
- Add the admin role check to all relevant commands
