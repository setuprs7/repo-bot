import discord
from discord import app_commands
import os
import json
import io
import aiohttp
from PIL import Image, ImageDraw

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

EMBED_COLOR = 0x2b2d31
CONFIG_FILE = "discord-bot/config.json"
ALLOWED_ROLE_ID = 1503070615106748546

NOTIFICATION_ROLES = [
    "Server Notice",
    "Giveaway Notice",
    "Event Notice",
    "Ajr Notice",
    "Games Notice",
    "Football Notice",
    "Live Notice",
]

SERVER_INFO_PAGES = [
    {
        "title": "Welcome to Our Server",
        "description": (
            "We're glad to have you here.\n\n"
            "This is a community built on respect, fun, and genuine connection. "
            "Whether you're here to socialize, watch live events, or be part of something bigger — you're in the right place.\n\n"
            "Use the pages below to learn everything before getting started."
        ),
        "footer": "Server Panel • Page 1 of 4",
    },
    {
        "title": "Server Sections",
        "description": (
            "**Announcements** — Official server news and updates\n\n"
            "**General Chat** — Open conversations with the community\n\n"
            "**Live & Sports** — Football and live event discussions\n\n"
            "**Gaming** — Gaming sessions and discussions\n\n"
            "**Events** — Competitions, giveaways, and activities\n\n"
            "**Voice Channels** — Hang out and talk with members"
        ),
        "footer": "Server Panel • Page 2 of 4",
    },
    {
        "title": "Notification Roles",
        "description": (
            "Stay updated by selecting your notification preferences:\n\n"
            "📢 **Server Notice** — Server announcements\n"
            "🎁 **Giveaway Notice** — Giveaway alerts\n"
            "🎉 **Event Notice** — Event alerts\n"
            "✨ **Ajr Notice** — Daily religious messages\n"
            "🎮 **Games Notice** — Gaming session alerts\n"
            "⚽ **Football Notice** — Football match notifications\n"
            "🔴 **Live Notice** — Live stream alerts\n\n"
            "Use the **Notifications** button on the main panel to manage your roles."
        ),
        "footer": "Server Panel • Page 3 of 4",
    },
    {
        "title": "Getting Started",
        "description": (
            "Here's how to get the most out of this server:\n\n"
            "1. Read the **Server Rules** carefully\n"
            "2. Select your **Notification** preferences\n"
            "3. Introduce yourself in the community\n"
            "4. Engage with members and enjoy the content\n"
            "5. Interested in staff? Use the **Apply** button\n\n"
            "If you have questions, reach out to any staff member."
        ),
        "footer": "Server Panel • Page 4 of 4",
    },
]


# ─── Config (persist apply channel per guild) ──────────────────────────────────

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_apply_channel(guild_id: int) -> int | None:
    config = load_config()
    return config.get(str(guild_id), {}).get("apply_channel")


def set_apply_channel(guild_id: int, channel_id: int):
    config = load_config()
    config.setdefault(str(guild_id), {})["apply_channel"] = channel_id
    save_config(config)


def get_welcome_channel(guild_id: int) -> int | None:
    config = load_config()
    return config.get(str(guild_id), {}).get("welcome_channel")


def set_welcome_channel(guild_id: int, channel_id: int):
    config = load_config()
    config.setdefault(str(guild_id), {})["welcome_channel"] = channel_id
    save_config(config)


# ─── Welcome image generation ──────────────────────────────────────────────────

WELCOME_TEMPLATE = "discord-bot/welcome_template.png"
# Circle where the avatar goes (top-left of the 500x281 image)
# Ring boundary detected at ~56px from center (72,78); avatar kept inside
AVATAR_CENTER_X = 80
AVATAR_CENTER_Y = 74
AVATAR_RADIUS   = 55   # slightly larger


async def build_welcome_image(avatar_url: str) -> io.BytesIO:
    # Download avatar
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    # Open avatar and make it circular
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    size = AVATAR_RADIUS * 2
    avatar = avatar.resize((size, size), Image.LANCZOS)

    # Create circular mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)

    # Apply mask
    avatar_circle = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    avatar_circle.paste(avatar, (0, 0), mask)

    # Paste onto template
    template = Image.open(WELCOME_TEMPLATE).convert("RGBA")
    x = AVATAR_CENTER_X - AVATAR_RADIUS
    y = AVATAR_CENTER_Y - AVATAR_RADIUS
    template.paste(avatar_circle, (x, y), avatar_circle)

    # Save to buffer
    buf = io.BytesIO()
    template.save(buf, format="PNG")
    buf.seek(0)
    return buf


@bot.event
async def on_member_join(member: discord.Member):
    channel_id = get_welcome_channel(member.guild.id)
    if not channel_id:
        return
    channel = member.guild.get_channel(channel_id)
    if not channel:
        return

    avatar_url = member.display_avatar.replace(size=256, format="png").url
    member_number = member.guild.member_count
    text = (
        f"✥ Welcome To RS Community\n"
        f"✥ Member : {member.mention}\n"
        f"✥ You are the member : #{member_number}\n"
        f"✥ Enjoy Your Stay"
    )
    try:
        image_buf = await build_welcome_image(avatar_url)
        await channel.send(
            content=text,
            file=discord.File(image_buf, filename="welcome.png")
        )
    except Exception as e:
        print(f"❌ Welcome image error: {e}")
        await channel.send(content=text)


# ─── Send application to staff channel ─────────────────────────────────────────

async def send_application(interaction: discord.Interaction, position: str, fields: dict):
    channel_id = get_apply_channel(interaction.guild_id)
    if not channel_id:
        return

    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=f"📋 New Application — {position}",
        color=0xe74c3c if position == "Moderation" else 0x3498db,
    )
    embed.set_author(
        name=str(interaction.user),
        icon_url=interaction.user.display_avatar.url,
    )
    for question, answer in fields.items():
        embed.add_field(name=question, value=answer or "—", inline=False)
    embed.set_footer(text=f"User ID: {interaction.user.id}")

    await channel.send(embed=embed)


# ─── Modals ─────────────────────────────────────────────────────────────────────

class ModeratorApplicationModal(discord.ui.Modal, title="Staff Application — Moderator"):
    name_age = discord.ui.TextInput(label="Your name and age", placeholder="Name, Age", required=True)
    why_mod = discord.ui.TextInput(label="Why do you want to be a Moderator?", style=discord.TextStyle.paragraph, required=True)
    handle_violations = discord.ui.TextInput(label="How do you handle rule violations?", style=discord.TextStyle.paragraph, required=True)
    hours = discord.ui.TextInput(label="How many hours per day are you available?", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Application submitted! The staff team will review it.", ephemeral=True)
        await send_application(interaction, "Moderation", {
            "Name & Age": str(self.name_age),
            "Why do you want to be a Moderator?": str(self.why_mod),
            "How do you handle rule violations?": str(self.handle_violations),
            "Hours available per day": str(self.hours),
        })


class EventTeamApplicationModal(discord.ui.Modal, title="Staff Application — Event Team"):
    name_age = discord.ui.TextInput(label="Your name and age", placeholder="Name, Age", required=True)
    event_types = discord.ui.TextInput(label="What types of events can you organize?", style=discord.TextStyle.paragraph, required=True)
    prior_exp = discord.ui.TextInput(label="Do you have prior experience in events?", style=discord.TextStyle.paragraph, required=True)
    stand_out = discord.ui.TextInput(label="What makes you stand out?", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Application submitted! The staff team will review it.", ephemeral=True)
        await send_application(interaction, "Event Team", {
            "Name & Age": str(self.name_age),
            "What types of events can you organize?": str(self.event_types),
            "Do you have prior experience in events?": str(self.prior_exp),
            "What makes you stand out?": str(self.stand_out),
        })


# ─── Embeds ─────────────────────────────────────────────────────────────────────

BANNER_URL = "https://i.imgur.com/lXlCWIt.gif"

def welcome_embed():
    e = discord.Embed(title="Welcome — Start-Up", color=EMBED_COLOR)
    e.description = "This is your starting point."
    e.set_image(url=BANNER_URL)
    e.set_footer(text="Server Panel • Start Here")
    return e


def rules_embed():
    e = discord.Embed(title="Server Rules", color=EMBED_COLOR)
    e.description = (
        "**I. Mutual Respect**\n"
        "All members must treat each other with respect. Insults, personal attacks, and provocations of any kind are strictly prohibited.\n\n"
        "**II. No Harassment**\n"
        "Harassment, bullying, racism, or any behavior that causes harm to others will result in an immediate ban.\n\n"
        "**III. Appropriate Content Only**\n"
        "Sharing offensive, adult, or ToS-violating content is not allowed in any channel under any circumstances.\n\n"
        "**IV. No Spam or Flooding**\n"
        "Repeated messages, excessive reactions, or irrelevant media outside designated channels is prohibited.\n\n"
        "**V. No Advertising**\n"
        "Promoting other servers, websites, or products without prior approval from the administration is not permitted.\n\n"
        "**VI. Channel Discipline**\n"
        "Each channel has a specific purpose — use it accordingly. Follow staff instructions at all times.\n\n"
        "**VII. Privacy & Security**\n"
        "Sharing private information about others or posting suspicious links is strictly forbidden.\n\n"
        "**VIII. Discord Guidelines**\n"
        "All members must comply with Discord Terms of Service and Community Guidelines."
    )
    e.set_footer(text="Server Panel • Please read carefully")
    return e


def apply_embed():
    e = discord.Embed(title="Staff Applications", color=EMBED_COLOR)
    e.description = (
        "Select the position you'd like to apply for:\n\n"
        "**Moderation** — Moderating the server and enforcing rules\n"
        "**Event Team** — Planning and running server events"
    )
    e.set_footer(text="Server Panel • Applications")
    return e


def notifications_embed():
    e = discord.Embed(title="Notification Roles", color=EMBED_COLOR)
    e.description = (
        "Select a role to add or remove it from your profile:\n\n"
        "— Server Notice\n"
        "— Giveaway Notice\n"
        "— Event Notice\n"
        "— Ajr Notice\n"
        "— Games Notice\n"
        "— Football Notice\n"
        "— Live Notice"
    )
    e.set_footer(text="Server Panel • Notifications")
    return e


def terms_embed(position: str):
    e = discord.Embed(title=f"Application Terms — {position}", color=EMBED_COLOR)
    e.description = (
        "Please read the following before submitting your application:\n\n"
        "— You must be an active member of the server\n"
        "— You must be at least 15 years old\n"
        "— You must be regularly available\n"
        "— All answers must be honest and accurate\n\n"
        "— If your application is rejected, no reason will be provided\n"
        "— Rejection does not reflect your value as a member\n"
        "— Do not apply unless you are serious about the commitment\n\n"
        "By clicking **I Agree**, you confirm that you have read and accept all of the above."
    )
    e.set_footer(text="Server Panel • Read carefully before proceeding")
    return e


# ─── Views ──────────────────────────────────────────────────────────────────────

class ModeratorTermsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="I Agree", style=discord.ButtonStyle.secondary)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModeratorApplicationModal())

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=apply_embed(), view=ApplyView())


class EventTeamTermsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="I Agree", style=discord.ButtonStyle.secondary)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EventTeamApplicationModal())

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=apply_embed(), view=ApplyView())


class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.secondary)
    async def moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=terms_embed("Moderation"), view=ModeratorTermsView())

    @discord.ui.button(label="Event Team", style=discord.ButtonStyle.secondary)
    async def event_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=terms_embed("Event Team"), view=EventTeamTermsView())


class NotificationRoleButton(discord.ui.Button):
    def __init__(self, role_name: str, row: int):
        super().__init__(label=role_name, style=discord.ButtonStyle.secondary, row=row)
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if not role:
            await interaction.response.send_message(f"❌ Role '{self.role_name}' not found in this server.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{self.role_name}**.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{self.role_name}**.", ephemeral=True)


class NotificationsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        rows = [0, 0, 0, 0, 1, 1, 1]
        for role_name, row in zip(NOTIFICATION_ROLES, rows):
            self.add_item(NotificationRoleButton(role_name, row))

    @discord.ui.button(label="Add All", style=discord.ButtonStyle.success, row=2)
    async def add_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        added = []
        for role_name in NOTIFICATION_ROLES:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role not in interaction.user.roles:
                await interaction.user.add_roles(role)
                added.append(role_name)
        msg = "✅ Added all notification roles." if added else "You already have all notification roles."
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="Remove All", style=discord.ButtonStyle.danger, row=2)
    async def remove_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        removed = []
        for role_name in NOTIFICATION_ROLES:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed.append(role_name)
        msg = "✅ Removed all notification roles." if removed else "You don't have any notification roles."
        await interaction.response.send_message(msg, ephemeral=True)


class ServerInfoView(discord.ui.View):
    def __init__(self, page: int = 0):
        super().__init__(timeout=180)
        self.page = page
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        total = len(SERVER_INFO_PAGES)
        back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        back.callback = self._back
        counter = discord.ui.Button(label=f"{self.page + 1} / {total}", style=discord.ButtonStyle.secondary, disabled=True)
        nxt = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, disabled=(self.page == total - 1))
        nxt.callback = self._next
        self.add_item(back)
        self.add_item(counter)
        self.add_item(nxt)

    def build_embed(self):
        p = SERVER_INFO_PAGES[self.page]
        e = discord.Embed(title=p["title"], description=p["description"], color=EMBED_COLOR)
        e.set_footer(text=p["footer"])
        return e

    async def _back(self, interaction: discord.Interaction):
        self.page -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next(self, interaction: discord.Interaction):
        self.page += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class MainPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Server Rules", style=discord.ButtonStyle.danger, custom_id="panel:rules")
    async def server_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=rules_embed(), ephemeral=True)

    @discord.ui.button(label="Server Info", style=discord.ButtonStyle.secondary, custom_id="panel:info")
    async def server_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ServerInfoView(page=0)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Notifications", style=discord.ButtonStyle.secondary, custom_id="panel:notifs")
    async def notifications(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=notifications_embed(), view=NotificationsView(), ephemeral=True)

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.secondary, custom_id="panel:apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=apply_embed(), view=ApplyView(), ephemeral=True)


# ─── Bot Events & Commands ──────────────────────────────────────────────────────

@bot.event
async def on_ready():
    bot.add_view(MainPanelView())
    # Remove any previously registered global commands (avoids duplicates)
    try:
        await bot.http.bulk_upsert_global_commands(bot.application_id, [])
        print("🗑️ Cleared global commands")
    except Exception as e:
        print(f"⚠️ Could not clear global commands: {e}")
    # Sync commands to each guild for instant visibility
    for guild in bot.guilds:
        try:
            tree.copy_global_to(guild=guild)
            synced = await tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} commands to: {guild.name} ({guild.id})")
            for cmd in synced:
                print(f"   - /{cmd.name}")
        except Exception as e:
            print(f"❌ Failed to sync to {guild.name}: {e}")
    print(f"البوت شغال: {bot.user} (ID: {bot.user.id})")


def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(r.id == ALLOWED_ROLE_ID for r in interaction.user.roles)


@tree.command(name="panel", description="Send the server panel")
async def panel_cmd(interaction: discord.Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ ما عندك صلاحية تستخدم هذا الأمر.", ephemeral=True)
        return
    await interaction.channel.send(embed=welcome_embed(), view=MainPanelView())
    await interaction.response.send_message("✅ تم إرسال اللوحة.", ephemeral=True)


@tree.command(name="setapplychannel", description="Set the channel where staff applications are sent")
@app_commands.describe(channel="The channel to receive staff applications")
async def setapplychannel_cmd(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ ما عندك صلاحية تستخدم هذا الأمر.", ephemeral=True)
        return
    set_apply_channel(interaction.guild_id, channel.id)
    embed = discord.Embed(
        title="✅ Apply Channel Set",
        description=f"Staff applications will now be sent to {channel.mention}.",
        color=0x2ecc71,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="setwelcomechannel", description="Set the channel where welcome messages are sent")
@app_commands.describe(channel="The channel to send welcome images")
async def setwelcomechannel_cmd(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ ما عندك صلاحية تستخدم هذا الأمر.", ephemeral=True)
        return
    set_welcome_channel(interaction.guild_id, channel.id)
    embed = discord.Embed(
        title="✅ Welcome Channel Set",
        description=f"Welcome images will now be sent to {channel.mention}.",
        color=0x2ecc71,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.environ["DISCORD_TOKEN"])
