import discord
from discord import app_commands
import asyncio
import datetime
from typing import Optional

# --- Данные (словарь для хранения состояния машин) ---
# В реальном проекте лучше использовать базу данных, чтобы данные не сбрасывались при перезапуске бота.
cars = {
    "Машина 1": {"status": "Свободна", "user": None, "time_left": None, "end_time": None},
    "Машина 2": {"status": "Свободна", "user": None, "time_left": None, "end_time": None},
    # ... добавьте до 12 машин
    "Машина 12": {"status": "Свободна", "user": None, "time_left": None, "end_time": None},
}

intents = discord.Intents.default()
intents.message_content = True # Обязательно для чтения сообщений!
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def generate_car_list():
    """Функция для создания красивого списка машин с их статусом."""
    lines = ["**Список машин:**"]
    for name, data in cars.items():
        status_emoji = "🟢" if data["status"] == "Свободна" else "🔴"
        time_info = ""
        if data["status"] == "Занята" and data["user"]:
            # Вычисляем оставшееся время
            if data["end_time"]:
                remaining = data["end_time"] - datetime.datetime.now()
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                time_info = f" (осталось: {minutes} мин {seconds} сек)"
            lines.append(f"{status_emoji} **{name}**: {data['status']} (взял: {data['user']}){time_info}")
        else:
            lines.append(f"{status_emoji} **{name}**: {data['status']}")
    return "\n".join(lines)

@client.event
async def on_ready():
    print(f'Бот {client.user} готов к работе!')
    await tree.sync() # Синхронизация слеш-команд
    # Запускаем фоновую задачу для обновления таймеров
    client.loop.create_task(update_timers())

async def update_timers():
    """Фоновая задача для обновления оставшегося времени каждую минуту."""
    await client.wait_until_ready()
    while not client.is_closed():
        # Каждую минуту обновляем сообщение в канале (по желанию)
        # Для простоты, мы просто ждем, но можно отправлять обновления в конкретный канал.
        await asyncio.sleep(60)
        # Здесь можно добавить логику автоматического освобождения машин по истечении времени
        # и отправку уведомлений.

@tree.command(name="cars", description="Показать список всех машин и их статус.")
async def cars_command(interaction: discord.Interaction):
    """Слеш-команда для отображения списка машин."""
    await interaction.response.send_message(generate_car_list())

@tree.command(name="take", description="Взять машину на определенное время.")
@app_commands.describe(car_name="Название машины", minutes="Время в минутах (от 15 до 120)")
async def take_command(interaction: discord.Interaction, car_name: str, minutes: app_commands.Range[int, 15, 120]):
    """Команда для взятия машины."""
    if car_name not in cars:
        await interaction.response.send_message(f"Машина '{car_name}' не найдена. Используйте /cars для просмотра списка.", ephemeral=True)
        return

    if cars[car_name]["status"] == "Занята":
        await interaction.response.send_message(f"Извините, машина '{car_name}' уже занята.", ephemeral=True)
        return

    # Бронируем машину
    user_name = interaction.user.display_name
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)

    cars[car_name]["status"] = "Занята"
    cars[car_name]["user"] = user_name
    cars[car_name]["end_time"] = end_time
    cars[car_name]["time_left"] = minutes

    await interaction.response.send_message(f"✅ Машина '{car_name}' успешно взята пользователем {user_name} на {minutes} минут!")

    # (Опционально) Можно сразу обновить сообщение со списком машин
    # channel = client.get_channel(ID_ВАШЕГО_КАНАЛА)
    # await channel.send(generate_car_list())

@tree.command(name="free", description="Освободить машину.")
@app_commands.describe(car_name="Название машины")
async def free_command(interaction: discord.Interaction, car_name: str):
    """Команда для освобождения машины."""
    if car_name not in cars:
        await interaction.response.send_message(f"Машина '{car_name}' не найдена.", ephemeral=True)
        return

    if cars[car_name]["status"] == "Свободна":
        await interaction.response.send_message(f"Машина '{car_name}' и так свободна.", ephemeral=True)
        return

    # Освобождаем машину
    cars[car_name]["status"] = "Свободна"
    cars[car_name]["user"] = None
    cars[car_name]["end_time"] = None
    cars[car_name]["time_left"] = None

    await interaction.response.send_message(f"✅ Машина '{car_name}' освобождена.")

# Запуск бота (не забудьте вставить ваш токен!)
client.run('fc9c9021468a7bc13a4fc233ca42ad5e9c76673c28cd2d106ec6d3ff9ce79ca9')