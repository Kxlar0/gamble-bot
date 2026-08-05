import os
import random
import discord
from discord import app_commands
from discord.ext import commands

# Set up intents
intents = discord.Intents.default()


class GambleBot(commands.Bot):

  def __init__(self):
    super().__init__(command_prefix="!", intents=intents)

  async def setup_hook(self):
    await self.tree.sync()
    print("Slash commands synced successfully!")


bot = GambleBot()

# In-memory database to store fake money balances {user_id: balance}
balances = {}

# --- OWNER & CHANNEL CONFIGURATION ---
OWNER_ID = 1079873848062783538  # Replace with your numeric Discord User ID
CO_OWNER_IDS = [
    # 123456789012345678, # Optional Co-Owners
]

# Put your designated gambling channel ID here!
# (Right-click your specific channel in Discord -> Copy Channel ID)
GAMBLE_CHANNEL_ID = YOUR_CHANNEL_ID_HERE


def is_owner_or_co_owner(user_id):
  return user_id == OWNER_ID or user_id in CO_OWNER_IDS


def get_balance(user_id):
  if user_id not in balances:
    balances[user_id] = 100  # Default starting balance is 100 fake coins
  return balances[user_id]


# --- CHANNEL CHECK HELPER ---
async def check_channel(interaction: discord.Interaction) -> bool:
  if interaction.channel_id != GAMBLE_CHANNEL_ID:
    await interaction.response.send_message(
        f"❌ You can only use gambling commands in <#{GAMBLE_CHANNEL_ID}>!",
        ephemeral=True,
    )
    return False
  return True


# --- BLACKJACK HELPER FUNCTIONS & VIEW ---

suits = ["♠", "♥", "♦", "♣"]
ranks = [
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
    "A",
]


def create_deck():
  deck = [(rank, suit) for suit in suits for rank in ranks]
  random.shuffle(deck)
  return deck


def calculate_hand(hand):
  value = 0
  aces = 0
  for card, _ in hand:
    if card in ["J", "Q", "K"]:
      value += 10
    elif card == "A":
      aces += 1
      value += 11
    else:
      value += int(card)

  while value > 21 and aces > 0:
    value -= 10
    aces -= 1

  return value


def format_hand(hand):
  return " ".join([f"`{rank}{suit}`" for rank, suit in hand])


class BlackjackView(discord.ui.View):

  def __init__(self, ctx_user, deck, player_hand, dealer_hand, bet):
    super().__init__(timeout=60)
    self.ctx_user = ctx_user
    self.deck = deck
    self.player_hand = player_hand
    self.dealer_hand = dealer_hand
    self.bet = bet
    self.game_over = False

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user.id != self.ctx_user.id:
      await interaction.response.send_message(
          "❌ This isn't your game!", ephemeral=True
      )
      return False
    return True

  def disable_items(self):
    for child in self.children:
      child.disabled = True

  @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
  async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
    if self.game_over:
      return

    self.player_hand.append(self.deck.pop())
    p_val = calculate_hand(self.player_hand)

    if p_val > 21:
      self.game_over = True
      balances[self.ctx_user.id] -= self.bet
      embed = discord.Embed(
          title="🃏 Blackjack - You Busted!",
          description=(
              f"**Your Hand:** {format_hand(self.player_hand)} (Score: `{p_val}`)\n"
              f"**Dealer's Hand:** {format_hand(self.dealer_hand)} (Score:"
              f" `{calculate_hand(self.dealer_hand)}`)\n\n💥 You went over 21"
              f" and lost **-{self.bet:,} fake coins**.\nNew balance:"
              f" **{balances[self.ctx_user.id]:,}**"
          ),
          color=discord.Color.red(),
      )
      self.disable_items()
      await interaction.response.edit_message(embed=embed, view=self)
    else:
      embed = discord.Embed(
          title="🃏 Blackjack",
          description=(
              f"**Your Hand:** {format_hand(self.player_hand)} (Score: `{p_val}`)\n"
              f"**Dealer's Card:** `{self.dealer_hand[0][0]}{self.dealer_hand[0][1]}`"
              " `?`\n\nChoose your move:"
          ),
          color=discord.Color.blue(),
      )
      await interaction.response.edit_message(embed=embed, view=self)

  @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
  async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
    if self.game_over:
      return

    self.game_over = True
    p_val = calculate_hand(self.player_hand)
    d_val = calculate_hand(self.dealer_hand)

    while d_val < 17:
      self.dealer_hand.append(self.deck.pop())
      d_val = calculate_hand(self.dealer_hand)

    if d_val > 21 or p_val > d_val:
      balances[self.ctx_user.id] += self.bet
      result_msg = f"🎉 Dealer busted or you had a higher score! You won **+{self.bet:,} fake coins**."
      color = discord.Color.green()
    elif p_val < d_val:
      balances[self.ctx_user.id] -= self.bet
      result_msg = (
          f"😢 Dealer had a higher score. You lost **-{self.bet:,} fake"
          f" coins**."
      )
      color = discord.Color.red()
    else:
      result_msg = "🤝 It's a Push (Tie)! Your bet is returned."
      color = discord.Color.gold()

    embed = discord.Embed(
        title="🃏 Blackjack - Game Over",
        description=(
            f"**Your Hand:** {format_hand(self.player_hand)} (Score:"
            f" `{p_val}`)\n**Dealer's Hand:**"
            f" {format_hand(self.dealer_hand)} (Score: `{d_val}`)\n\n{result_msg}\nNew"
            f" balance: **{balances[self.ctx_user.id]:,}**"
        ),
        color=color,
    )
    self.disable_items()
    await interaction.response.edit_message(embed=embed, view=self)


# --- BOT EVENTS & COMMANDS ---


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("gamblebot.py is online and ready!")


@bot.tree.command(name="balance", description="Check your current fake money balance")
async def balance(interaction: discord.Interaction):
  bal = get_balance(interaction.user.id)
  embed = discord.Embed(
      title=f"💰 {interaction.user.name}'s Wallet",
      description=f"You have **{bal:,} fake coins**.",
      color=discord.Color.gold(),
  )
  await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="View the richest players on the server")
async def leaderboard(interaction: discord.Interaction):
  if not balances:
    await interaction.response.send_message(
        "❌ No one has any fake coins yet!", ephemeral=True
    )
    return

  sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)

  leaderboard_text = ""
  for rank, (user_id, bal) in enumerate(sorted_balances[:10], start=1):
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`#{rank}`"
    leaderboard_text += f"{medal} <@{user_id}> — **{bal:,} fake coins**\n"

  embed = discord.Embed(
      title="🏆 Richest Players Leaderboard",
      description=leaderboard_text,
      color=discord.Color.gold(),
  )
  await interaction.response.send_message(embed=embed)


@bot.tree.command(name="daily", description="Collect your daily allowance of fake money")
async def daily(interaction: discord.Interaction):
  if not await check_channel(interaction):
    return

  user_id = interaction.user.id
  get_balance(user_id)

  balances[user_id] += 500
  embed = discord.Embed(
      title="🎁 Daily Reward!",
      description=(
          "You collected your daily allowance of **500 fake coins**!\nYour new"
          f" balance is **{balances[user_id]:,} fake coins**."
      ),
      color=discord.Color.green(),
  )
  await interaction.response.send_message(embed=embed)


@bot.tree.command(name="coinflip", description="Gamble your fake money on a coinflip")
@app_commands.describe(
    choice="Choose heads or tails", amount="Amount of fake coins to bet"
)
@app_commands.choices(
    choice=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ]
)
async def coinflip(interaction: discord.Interaction, choice: app_commands.Choice[str], amount: int):
  if not await check_channel(interaction):
    return

  user_id = interaction.user.id
  user_choice = choice.value

  if amount <= 0:
    await interaction.response.send_message(
        "❌ You must bet a positive amount of fake coins.", ephemeral=True
    )
    return

  current_bal = get_balance(user_id)
  if amount > current_bal:
    await interaction.response.send_message(
        f"❌ You don't have enough fake coins! Your balance is"
        f" **{current_bal:,}**.",
        ephemeral=True,
    )
    return

  result = random.choice(["tails", "heads"])

  if user_choice == result:
    balances[user_id] += amount
    embed = discord.Embed(
        title="🎉 You Won!",
        description=(
            f"The coin landed on **{result.upper()}**!\nYou guessed correctly"
            f" and won **+{amount:,} fake coins**.\nNew balance:"
            f" **{balances[user_id]:,}**"
        ),
        color=discord.Color.green(),
    )
  else:
    balances[user_id] -= amount
    embed = discord.Embed(
        title="😢 You Lost!",
        description=(
            f"The coin landed on **{result.upper()}**.\nYou guessed wrong and"
            f" lost **-{amount:,} fake coins**.\nNew balance:"
            f" **{balances[user_id]:,}**"
        ),
        color=discord.Color.red(),
    )

  await interaction.response.send_message(embed=embed)


@bot.tree.command(name="blackjack", description="Play a game of Blackjack against the dealer")
@app_commands.describe(amount="Amount of fake coins to bet")
async def blackjack(interaction: discord.Interaction, amount: int):
  if not await check_channel(interaction):
    return

  user_id = interaction.user.id

  if amount <= 0:
    await interaction.response.send_message(
        "❌ You must bet a positive amount of fake coins.", ephemeral=True
    )
    return

  current_bal = get_balance(user_id)
  if amount > current_bal:
    await interaction.response.send_message(
        f"❌ You don't have enough fake coins! Your balance is"
        f" **{current_bal:,}**.",
        ephemeral=True,
    )
    return

  deck = create_deck()
  player_hand = [deck.pop(), deck.pop()]
  dealer_hand = [deck.pop(), deck.pop()]

  p_val = calculate_hand(player_hand)

  if p_val == 21:
    balances[user_id] += amount
    embed = discord.Embed(
        title="🃏 Blackjack - Natural 21!",
        description=(
            f"**Your Hand:** {format_hand(player_hand)} (Score: `21`)\n"
            f"**Dealer's Hand:** {format_hand(dealer_hand)} (Score:"
            f" `{calculate_hand(dealer_hand)}`)\n\n🎉 Natural Blackjack! You"
            f" won **+{amount:,} fake coins**.\nNew balance:"
            f" **{balances[user_id]:,}**"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed)
    return

  view = BlackjackView(interaction.user, deck, player_hand, dealer_hand, amount)
  embed = discord.Embed(
      title="🃏 Blackjack",
      description=(
          f"**Your Hand:** {format_hand(player_hand)} (Score: `{p_val}`)\n"
          f"**Dealer's Card:** `{dealer_hand[0][0]}{dealer_hand[0][1]}` `?`\n\nChoose"
          " your move:"
      ),
      color=discord.Color.blue(),
  )
  await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="givecoins", description="[Owner/Co-Owner Only] Give fake coins to a user")
@app_commands.describe(
    member="The user to give coins to", amount="Amount of fake coins to add"
)
async def givecoins(interaction: discord.Interaction, member: discord.Member, amount: int):
  if not is_owner_or_co_owner(interaction.user.id):
    await interaction.response.send_message(
        "❌ You do not have permission to use this command!", ephemeral=True
    )
    return

  if amount <= 0:
    await interaction.response.send_message(
        "❌ You must specify a positive amount of coins.", ephemeral=True
    )
    return

  target_id = member.id
  get_balance(target_id)
  balances[target_id] += amount

  embed = discord.Embed(
      title="💸 Coins Added!",
      description=(
          f"Successfully added **{amount:,} fake coins** to {member.mention}'s"
          f" account.\nNew balance: **{balances[target_id]:,} fake coins**"
      ),
      color=discord.Color.gold(),
  )
  await interaction.response.send_message(embed=embed)


# Securely run bot using Render's environment variable
bot.run(os.getenv("MTUzNDQwNDk4NjUxMzkyMDA1MA.GEjkEu.8HU9ZFN7XoiX7-pCWt3oepjKJMudfMkF-WBj4c"))
