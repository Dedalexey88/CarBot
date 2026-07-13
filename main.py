import os
import discord
from discord import app_commands
import asyncio
import datetime

# Данные о машинах
cars = {
    "Машина 1": {"status": "Свободна", "user": None, "time_left": None, "end_time": None},
    "Машина 2": {"status": "Свободна", "user": None, "time_left": None, "end_time": None},
    # ... до Машина 12
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    await tree.sync()

@tree.command(name="cars", description="Показать список всех машин")
async def cars_command(interaction: discord.Interaction):
    # ... ваш код для списка машин
    await interaction.response.send_message("Список машин...")

# ЗАПУСК - ТОКЕН ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ!
client.run(os.getenv('DISCORD_TOKEN'))