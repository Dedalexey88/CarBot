import os
import discord
from discord import app_commands
import datetime

# --- Данные о машинах (12 штук) ---
cars = {
    "Karin Rebel TS701VCA": {"status": "Свободна", "user": None, "end_time": None},
    "Benefactor Ml63 2010 ST530MFA": {"status": "Свободна", "user": None, "end_time": None},
    "Annis Jook Nizmo RS 2013 JZ738CKY": {"status": "Свободна", "user": None, "end_time": None},
    "Emperor IC-F 2012 BU363YHX": {"status": "Свободна", "user": None, "end_time": None},
    "Benefactor G-series 63 ASG 6x6 LY699IEB": {"status": "Свободна", "user": None, "end_time": None},
    "Vapid Bronzo Predator 2022 GC643UFN": {"status": "Свободна", "user": None, "end_time": None},
    "Karin Thunder 2021 SY108SFL": {"status": "Свободна", "user": None, "end_time": None},
    "Ocelot Lynx 2019 HK742XAM": {"status": "Свободна", "user": None, "end_time": None},
    "Grotti Turismo R 2018 PM930SRL": {"status": "Свободна", "user": None, "end_time": None},
    "Pegassi Tempesta 2020 YF521KCD": {"status": "Свободна", "user": None, "end_time": None},
    "Pfister Comet SR 2022 XE876BFT": {"status": "Свободна", "user": None, "end_time": None},
    "Dewbauchee Vagner 2023 TD210MXP": {"status": "Свободна", "user": None, "end_time": None},
}

# --- Настройка бота ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Функция для создания списка машин ---
def generate_car_list():
    """Генерирует красивое сообщение со списком всех машин."""
    lines = ["**🚗 Список машин:**"]
    
    for name, data in cars.items():
        status_emoji = "🟢" if data["status"] == "Свободна" else "🔴"
        
        if data["status"] == "Занята" and data["user"]:
            time_left = ""
            if data["end_time"]:
                remaining = data["end_time"] - datetime.datetime.now()
                if remaining.total_seconds() > 0:
                    minutes = int(remaining.total_seconds() // 60)
                    seconds = int(remaining.total_seconds() % 60)
                    time_left = f" (осталось: {minutes} мин {seconds} сек)"
                else:
                    time_left = " ⏰ ВРЕМЯ ВЫШЛО!"
            
            lines.append(f"{status_emoji} **{name}**: {data['status']} (взял: {data['user']}){time_left}")
        else:
            lines.append(f"{status_emoji} **{name}**: {data['status']}")
    
    return "\n".join(lines)

# --- Событие: бот готов ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    await tree.sync()

# --- КОМАНДА: /cars (ПРАВИЛЬНАЯ ВЕРСИЯ) ---
@tree.command(name="cars", description="Показать список всех машин и их статус")
async def cars_command(interaction: discord.Interaction):
    """Отображает список всех машин."""
    car_list = generate_car_list()  # ВАЖНО: вызываем функцию!
    await interaction.response.send_message(car_list)  # ВАЖНО: отправляем результат!

# --- КОМАНДА: /take ---
@tree.command(name="take", description="Взять машину на определенное время")
@app_commands.describe(
    car_name="Название машины",
    minutes="Время в минутах (от 15 до 120)"
)
async def take_command(
    interaction: discord.Interaction, 
    car_name: str, 
    minutes: app_commands.Range[int, 15, 120]
):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена. Используйте /cars для просмотра.",
            ephemeral=True
        )
        return

    if cars[car_name]["status"] == "Занята":
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' уже занята.",
            ephemeral=True
        )
        return

    user_name = interaction.user.display_name
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)

    cars[car_name]["status"] = "Занята"
    cars[car_name]["user"] = user_name
    cars[car_name]["end_time"] = end_time

    await interaction.response.send_message(
        f"✅ Машина '{car_name}' взята пользователем **{user_name}** на **{minutes}** минут!"
    )

# --- КОМАНДА: /free ---
@tree.command(name="free", description="Освободить машину")
@app_commands.describe(car_name="Название машины")
async def free_command(interaction: discord.Interaction, car_name: str):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена.",
            ephemeral=True
        )
        return

    if cars[car_name]["status"] == "Свободна":
        await interaction.response.send_message(
            f"✅ Машина '{car_name}' уже свободна.",
            ephemeral=True
        )
        return

    cars[car_name]["status"] = "Свободна"
    cars[car_name]["user"] = None
    cars[car_name]["end_time"] = None

    await interaction.response.send_message(
        f"✅ Машина '{car_name}' освобождена!"
    )

# --- ЗАПУСК БОТА ---
client.run(os.getenv('DISCORD_TOKEN'))