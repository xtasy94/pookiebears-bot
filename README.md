# CTFtime Discord Bot

This Discord bot provides information about Capture The Flag (CTF) events and teams using data from CTFtime.org. It offers features such as event announcements, team rankings, and more to keep your Discord community updated on the latest in the CTF world.

## Features

- Automatically announce upcoming CTF events
- Display top CTF teams globally and by country
- Show detailed information about specific CTF teams
- Customizable prefix for commands
- Configurable announcement channel

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/xtasy94/pookiebears-bot
   cd pookiebears-bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a Discord application and bot at the [Discord Developer Portal](https://discord.com/developers/applications).

4. Copy your bot token and replace `'REDACTED'` in the `TOKEN` variable in `main.py` with your actual bot token.

5. Invite the bot to your Discord server using the OAuth2 URL generator in the Discord Developer Portal. Ensure it has the necessary permissions (Send Messages, Embed Links, etc.).

6. Run the bot:
   ```
   python main.py
   ```

## Commands

- `!help`: Display a list of available commands and their descriptions.
- `!test`: Manually fetch and post the latest CTF events (requires Manage Server permission).
- `!topcountryteams [country_code]`: Display ranked CTF teams for a specified country code.
- `!topteams [year] [limit]`: Display top CTF teams for a specified year (defaults to current year if omitted).
- `!team [team_id]`: Display detailed information about a specific team by its ID.
- `!uptime`: Display how long the bot has been running.
- `!setprefix [new_prefix]`: Set a new prefix for the bot (requires Manage Server permission).
- `!setannouncementchannel [#channel]`: Set the announcement channel for CTF events (requires Manage Server permission).

Note: The default prefix is `!`. You can change it using the `setprefix` command.

## Configuration

The bot uses two JSON files for configuration:

1. `server_config.json`: Stores server-specific settings like custom prefixes and announcement channel IDs.
2. `announced_events.json`: Keeps track of announced events to avoid duplicates.

These files are created automatically when needed.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is not officially affiliated with CTFtime.org. It uses the CTFtime API to fetch publicly available data. Please use responsibly and in accordance with CTFtime's terms of service.