import discord
import requests
import json
import os
import math
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from datetime import datetime, timedelta, timezone
from discord import ButtonStyle
from discord.ui import Button, View

TOKEN = 'REDACTED'
CTFTIME_API_EVENTS = "https://ctftime.org/api/v1/events/"
CTFTIME_API_TOP_TEAMS = "https://ctftime.org/api/v1/top/"
CTFTIME_API_TEAM_INFO = "https://ctftime.org/api/v1/teams/"
CTFTIME_API_TOP_BY_COUNTRY = "https://ctftime.org/api/v1/top-by-country/"
ANNOUNCED_EVENTS_FILE = 'announced_events.json'
SERVER_CONFIG_FILE = 'server_config.json'

intents = discord.Intents.default()
intents.message_content = True

def get_prefix(bot, message):
    if not message.guild:
        return '!'  # Default prefix for DMs
    with open(SERVER_CONFIG_FILE, 'r') as f:
        server_config = json.load(f)
    return server_config.get(str(message.guild.id), {}).get('prefix', '!')

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

start_time = datetime.now(timezone.utc)

def load_server_config():
    if not os.path.exists(SERVER_CONFIG_FILE):
        with open(SERVER_CONFIG_FILE, 'w') as f:
            json.dump({}, f)
    with open(SERVER_CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_server_config(config):
    with open(SERVER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_announced_events():
    if not os.path.exists(ANNOUNCED_EVENTS_FILE):
        with open(ANNOUNCED_EVENTS_FILE, 'w') as f:
            json.dump({"announced_event_ids": []}, f)
    with open(ANNOUNCED_EVENTS_FILE, 'r') as f:
        data = json.load(f)
    return set(data.get("announced_event_ids", []))

def save_announced_events(announced_event_ids):
    with open(ANNOUNCED_EVENTS_FILE, 'w') as f:
        json.dump({"announced_event_ids": list(announced_event_ids)}, f, indent=4)

def get_ctftime_events():
    try:
        headers = {
            "User-Agent": "DiscordBot (https://yourbotwebsite.com, v1.0)"
        }
        now = datetime.now(timezone.utc)
        start = int(now.timestamp())
        finish = int((now + timedelta(days=7)).timestamp())
        params = {
            "limit": 100,
            "start": start,
            "finish": finish
        }
        response = requests.get(CTFTIME_API_EVENTS, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching CTFtime events: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error occurred while fetching events: {e}")
        return []

def create_ctf_embed(event):
    embed = discord.Embed(
        title=event["title"],
        description=event.get("description", "No description provided."),
        url=event["ctftime_url"],
        color=discord.Color.blue(),
        timestamp=datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
    )

    embed.add_field(name="Start", value=event["start"], inline=True)
    embed.add_field(name="End", value=event["finish"], inline=True)
    embed.add_field(name="Format", value=event["format"], inline=True)
    embed.add_field(name="Participants", value=event.get("participants", "N/A"), inline=True)
    embed.add_field(name="Weight", value=event.get("weight", "N/A"), inline=True)
    embed.add_field(name="Prizes", value=event.get("prizes", "No prizes"), inline=False)
    embed.add_field(name="Location", value=event.get("location", "Online"), inline=True)
    embed.add_field(name="URL", value=event.get("url", "N/A"), inline=True)

    organizers = ', '.join([org["name"] for org in event.get("organizers", [])])
    embed.add_field(name="Organizers", value=organizers if organizers else "N/A", inline=False)

    logo_url = event.get("logo", "")
    if logo_url:
        embed.set_thumbnail(url=logo_url)
    else:
        embed.set_thumbnail(url="https://ctftime.org/static/images/logo.png")

    return embed

def get_top_teams(year=None, limit=10):
    try:
        url = CTFTIME_API_TOP_TEAMS
        if year:
            url += f"{year}/"
        headers = {
            "User-Agent": "DiscordBot (https://yourbotwebsite.com, v1.0)"
        }
        params = {"limit": limit}
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching top teams: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error occurred while fetching top teams: {e}")
        return {}


class TopTeamsPaginator(View):
    def __init__(self, teams, year, limit):
        super().__init__(timeout=60)  
        self.teams = teams
        self.year = year
        self.limit = limit
        self.current_page = 0
        self.teams_per_page = 10 

    @discord.ui.button(label="Previous", style=ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next", style=ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if (self.current_page + 1) * self.teams_per_page < self.limit:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    def create_embed(self):
        start_idx = self.current_page * self.teams_per_page
        end_idx = start_idx + self.teams_per_page
        current_teams = self.teams[start_idx:end_idx]

        embed = discord.Embed(
            title=f"Top CTF Teams for {self.year}",
            color=discord.Color.purple(),
            timestamp=datetime.now(timezone.utc)
        )

        for idx, team in enumerate(current_teams, start=start_idx + 1):
            embed.add_field(
                name=f"{idx}. {team['team_name']}",
                value=f"Points: {team['points']:.2f} | Team ID: {team['team_id']}",
                inline=False
            )

        total_pages = (self.limit - 1) // self.teams_per_page + 1
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages} | Data from CTFtime.org")
        return embed


def get_team_info(team_id):
    try:
        url = f"{CTFTIME_API_TEAM_INFO}{team_id}/"
        headers = {
            "User-Agent": "DiscordBot (https://yourbotwebsite.com, v1.0)"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching team info: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error occurred while fetching team info: {e}")
        return {}

def get_top_teams_by_country(country_code):
    try:
        url = f"{CTFTIME_API_TOP_BY_COUNTRY}{country_code}/"
        headers = {
            "User-Agent": "DiscordBot (https://yourbotwebsite.com, v1.0)"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching top teams by country: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error occurred while fetching top teams by country: {e}")
        return []

class TeamPaginator(View):
    def __init__(self, teams, country_code):
        super().__init__(timeout=60)
        self.teams = teams
        self.country_code = country_code
        self.current_page = 0
        self.teams_per_page = 10

    @discord.ui.button(label="Previous", style=ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next", style=ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if (self.current_page + 1) * self.teams_per_page < len(self.teams):
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    def create_embed(self):
        start_idx = self.current_page * self.teams_per_page
        end_idx = start_idx + self.teams_per_page
        current_teams = self.teams[start_idx:end_idx]

        embed = discord.Embed(
            title=f"Top CTF Teams for {self.country_code.upper()}",
            color=discord.Color.teal(),
            timestamp=datetime.now(timezone.utc)
        )

        for team in current_teams:
            embed.add_field(
                name=f"{team['country_place']}. {team['team_name']}",
                value=f"Global Rank: {team['place']}\nPoints: {team['points']:.2f}\nEvents: {team['events']}",
                inline=False
            )

        total_pages = (len(self.teams) - 1) // self.teams_per_page + 1
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages} | Data from CTFtime.org")
        return embed
    
def calculate_rating(weight, total_teams, best_points, team_place, team_points):

    points_coef = team_points / best_points if best_points > 0 else 0

    place_coef = 1 / team_place if team_place > 0 else 0

    if points_coef > 0:
        e_rating = ((points_coef + place_coef) * weight) / (1 / (1 + team_place/total_teams))
        return e_rating
    return 0

@bot.command(name='topcountryteams')
async def top_country_teams_command(ctx, country_code: str):
    await ctx.send(f"Fetching top teams for country code: {country_code.upper()}...")
    teams = get_top_teams_by_country(country_code.lower())
    
    if not teams:
        await ctx.send(f"No data found or an error occurred while fetching top teams for country code: {country_code.upper()}")
        return

    paginator = TeamPaginator(teams, country_code)
    await ctx.send(embed=paginator.create_embed(), view=paginator)

@bot.command(name='help')
async def help_command(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(
        title="CTFtime Bot Help",
        description=f"List of available commands (current prefix: {prefix}):",
        color=discord.Color.green()
    )
    embed.add_field(name=f"{prefix}help", value="Display this help message.", inline=False)
    embed.add_field(name=f"{prefix}test", value="Manually fetch and post the latest CTF events. (Requires Manage Server permission)", inline=False)
    embed.add_field(name=f"{prefix}topcountryteams [country_code]", value="Display ranked CTF teams for a specified country code, with pagination.", inline=False)
    embed.add_field(name=f"{prefix}topteams [year] [limit]", value="Display top CTF teams for a specified year. If year is omitted, current year is used. Limit defaults to 10.", inline=False)
    embed.add_field(name=f"{prefix}team [team_id]", value="Display detailed information about a specific team by its ID.", inline=False)
    embed.add_field(name=f"{prefix}uptime", value="Display how long the bot has been running.", inline=False)
    embed.add_field(name=f"{prefix}setprefix [new_prefix]", value="Set a new prefix for the bot. (Requires Manage Server permission)", inline=False)
    embed.add_field(name=f"{prefix}setannouncementchannel [#channel]", value="Set the announcement channel for CTF events. (Requires Manage Server permission)", inline=False)
    embed.add_field(name=f"{prefix}rating [weight] [total_teams] [best_points] [team_place] [team_points]", value="Calculate the rating points of a particular team in an event using the [CTFtime rating formula.](https://ctftime.org/rating-formula/)", inline=False)
    embed.set_footer(text="CTFtime Discord Bot")
    await ctx.send(embed=embed)

@bot.command(name='test')
@has_permissions(manage_guild=True)
async def test_command(ctx):
    message = await ctx.send("Fetching and posting the latest CTF events starting within a week...")
    events_found = await post_ctf_events(ctx.guild.id, message)
    if not events_found:
        await message.edit(content="No new CTF events starting within a week.")

@test_command.error
async def test_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")

@bot.command(name='topteams')
async def top_teams_command(ctx, year: int = None, limit: int = 10):
    if year is None:
        year = datetime.now(timezone.utc).year
    if limit < 1:
        await ctx.send("Limit must be at least 1.")
        return
    await ctx.send(f"Fetching top {limit} teams for the year {year}...")
    data = get_top_teams(year=year, limit=limit)
    if not data:
        await ctx.send("No data found or an error occurred while fetching top teams.")
        return

    year_str = str(year)
    if year_str not in data:
        await ctx.send(f"No data available for the year {year}.")
        return

    teams = data[year_str]
    if not teams:
        await ctx.send(f"No teams found for the year {year}.")
        return

    # If the total teams exceed teams_per_page, use paginator
    if limit > 10:
        paginator = TopTeamsPaginator(teams, year, limit)
        embed = paginator.create_embed()
        await ctx.send(embed=embed, view=paginator)
    else:
        embed = discord.Embed(
            title=f"Top {limit} CTF Teams for {year}",
            color=discord.Color.purple(),
            timestamp=datetime.now(timezone.utc)
        )

        for idx, team in enumerate(teams, start=1):
            embed.add_field(
                name=f"{idx}. {team['team_name']}",
                value=f"Points: {team['points']:.2f} | Team ID: {team['team_id']}",
                inline=False
            )

        embed.set_footer(text="Data from CTFtime.org")
        await ctx.send(embed=embed)

@bot.command(name='team')
async def team_info_command(ctx, team_id: int):
    await ctx.send(f"Fetching information for Team ID: {team_id}...")
    team = get_team_info(team_id)
    if not team:
        await ctx.send("No data found or an error occurred while fetching team information.")
        return

    embed = discord.Embed(
        title=team.get("name", "N/A"),
        description=f"**Primary Alias:** {team.get('primary_alias', 'N/A')}",
        url=f"https://ctftime.org/team/{team_id}/",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(name="Country", value=team.get("country", "N/A"), inline=True)
    embed.add_field(name="Academic", value=team.get("academic", False), inline=True)
    embed.add_field(name="Aliases", value=', '.join(team.get("aliases", [])), inline=False)

    rating = team.get("rating", {})
    latest_year = max([int(year) for year in rating.keys() if year.isdigit()], default=None)
    if latest_year:
        latest_rating = rating[str(latest_year)]
        embed.add_field(name=f"Rating ({latest_year})", value=f"Place: {latest_rating.get('rating_place', 'N/A')}\nPoints: {latest_rating.get('rating_points', 'N/A')}\nCountry Place: {latest_rating.get('country_place', 'N/A')}", inline=False)

    logo_url = team.get("logo", "")
    if logo_url:
        embed.set_thumbnail(url=logo_url)
    else:
        embed.set_thumbnail(url="https://ctftime.org/static/images/logo.png")

    embed.set_footer(text="Data fetched from CTFtime.org")
    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime_command(ctx):
    current_time = datetime.now(timezone.utc)
    uptime = current_time - start_time
    days, hours, minutes, seconds = uptime.days, uptime.seconds // 3600, (uptime.seconds // 60) % 60, uptime.seconds % 60
    
    embed = discord.Embed(
        title="Bot Uptime",
        description=f"The bot has been running for:\n{days} days, {hours} hours, {minutes} minutes, and {seconds} seconds.",
        color=discord.Color.green(),
        timestamp=current_time
    )
    embed.set_footer(text="CTFtime Discord Bot")
    await ctx.send(embed=embed)

@bot.command(name='setprefix')
@has_permissions(manage_guild=True)
async def set_prefix(ctx, new_prefix: str):
    if len(new_prefix) > 5:
        await ctx.send("Prefix must be 5 characters or less.")
        return
    
    config = load_server_config()
    server_id = str(ctx.guild.id)
    if server_id not in config:
        config[server_id] = {}
    config[server_id]['prefix'] = new_prefix
    save_server_config(config)
    
    await ctx.send(f"Prefix has been set to '{new_prefix}'")

@bot.command(name='setannouncementchannel')
@has_permissions(manage_guild=True)
async def set_announcement_channel(ctx, channel: discord.TextChannel):
    config = load_server_config()
    server_id = str(ctx.guild.id)
    if server_id not in config:
        config[server_id] = {}
    config[server_id]['announcement_channel_id'] = channel.id
    save_server_config(config)
    
    await ctx.send(f"Announcement channel has been set to {channel.mention}")

async def post_ctf_events(specific_server_id=None, message=None):
    config = load_server_config()
    events_found = False

    for server_id, server_config in config.items():
        if specific_server_id and str(specific_server_id) != server_id:
            continue

        announcement_channel_id = server_config.get('announcement_channel_id')
        if announcement_channel_id:
            channel = bot.get_channel(announcement_channel_id)
            if channel is None:
                print(f"Announcement channel with ID {announcement_channel_id} not found for server {server_id}.")
                continue

            announced_event_ids = load_announced_events()
            events = get_ctftime_events()

            new_events = []
            for event in events:
                event_id = event["id"]
                if event_id not in announced_event_ids:
                    new_events.append(event)
                    announced_event_ids.add(event_id)

            if not new_events:
                print(f"No new CTF events to announce for server {server_id}.")
                continue

            events_found = True
            for event in new_events:
                embed = create_ctf_embed(event)
                try:
                    await channel.send(embed=embed)
                    print(f"Announced event: {event['title']} in server {server_id}")
                except Exception as e:
                    print(f"Failed to send embed for event {event['title']} in server {server_id}: {e}")

            save_announced_events(announced_event_ids)

    return events_found

@tasks.loop(hours=1)
async def fetch_events_periodically():
    print("Automatically fetching and posting new CTF events starting within a week...")
    await post_ctf_events()

@bot.command(name='rating')
async def rating(ctx, weight: str = None, total_teams: str = None, 
                best_points: str = None, team_place: str = None, 
                team_points: str = None):

    error_embed = discord.Embed(
        title="Error",
        color=discord.Color.red()
    )
    error_embed.add_field(
    name="Please check your command",
    value="Either the variables aren't properly given or there is some internal error.\n\n"
          "The command format should be:\n"
          "`!rating [weight] [total_teams] [best_points] [team_place] [team_points]`\n\n"
          "Please contact @sickinsecure on Discord if you feel like the bot has some bug.",
    inline=False
)

    if None in [weight, total_teams, best_points, team_place, team_points]:
        await ctx.send(embed=error_embed)
        return

    try:

        weight = float(weight)
        total_teams = float(total_teams)
        best_points = float(best_points)
        team_place = float(team_place)
        team_points = float(team_points)

        if any(x <= 0 for x in [total_teams, best_points, team_place]):
            await ctx.send(embed=error_embed)
            return

        e_rating = calculate_rating(weight, total_teams, best_points, team_place, team_points)

        result_embed = discord.Embed(
            title="Rating Calculation Results",
            color=discord.Color.blue()
        )

        result_embed.add_field(
            name="Input Parameters",
            value=f"Weight: {weight:.4f}\n"
                  f"Total Teams: {total_teams:.4f}\n"
                  f"Best Points: {best_points:.4f}\n"
                  f"Team Place: {team_place:.4f}\n"
                  f"Team Points: {team_points:.4f}",
            inline=False
        )

        points_coef = team_points / best_points if best_points > 0 else 0
        place_coef = 1 / team_place if team_place > 0 else 0

        result_embed.add_field(
            name="Calculations",
            value=f"Points Coefficient: {points_coef:.4f}\n"
                  f"Place Coefficient: {place_coef:.4f}",
            inline=False
        )

        result_embed.add_field(
            name="Final E Rating",
            value=f"**{e_rating:.4f}**",
            inline=False
        )

        await ctx.send(embed=result_embed)

    except ValueError:
        await ctx.send(embed=error_embed)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        await ctx.send(embed=error_embed)

@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    fetch_events_periodically.start()

bot.run(TOKEN)