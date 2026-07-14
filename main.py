import os
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import datetime
import asyncio

# --- ID из переменных окружения ---
GUILD_ID = int(os.getenv('GUILD_ID', 0))
CONTRACT_CHANNEL_ID = int(os.getenv('CONTRACT_CHANNEL_ID', 0))
CAR_CHANNEL_ID = int(os.getenv('CAR_CHANNEL_ID', 0))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# --- Данные о машинах ---
cars = {
    "Karin Rebel TS701VCA": {"status": "Свободна", "user": None, "end_time": None},
    "Benefactor Ml63 2010 ST530MFA": {"status": "Свободна", "user": None, "end_time": None},
    "Annis Jook Nizmo RS 2013 JZ738CKY": {"status": "Свободна", "user": None, "end_time": None},
    "Emperor IC-F 2012 BU363YHX": {"status": "Свободна", "user": None, "end_time": None},
    "Benefactor G-series 63 ASG 6x6 LY699IEB": {"status": "Свободна", "user": None, "end_time": None},
    "Vapid Bronzo Predator 2022 GC643UFN": {"status": "Свободна", "user": None, "end_time": None},
    "Karin Thunder 2021 SY108SFL": {"status": "Свободна", "user": None, "end_time": None},
}

# --- Данные для контрактов ---
contracts = {}

# --- НАСТРОЙКА БОТА (СНАЧАЛА!) ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)  # <-- tree СОЗДАЕТСЯ ЗДЕСЬ!

# --- ДАЛЬШЕ ВСЕ КОМАНДЫ И ФУНКЦИИ ---

# --- Функция для отправки сообщения в лог-канал ---
async def send_log(message: str, embed: discord.Embed = None):
    # ... код ...

# --- Функция очистки ---
async def cleanup_channel(channel_id: int, keep_last: int = 10, exclude_ids: list = None):
    # ... код ...

# --- Функция для создания списка машин ---
def generate_car_list():
    # ... код ...

# --- Функция для освобождения машины ---
async def free_car_auto(car_name: str):
    # ... код ...

# --- Обновление канала с машинами ---
async def update_cars_channel():
    # ... код ...

# --- Автоматический таймер ---
async def auto_free_timer(car_name: str, minutes: int):
    # ... код ...

# --- Класс для кнопок времени ---
class TimeButtonsView(View):
    # ... код ...

# --- Модальное окно для навыков ---
class SkillModal(Modal):
    # ... код ...

# --- Кнопка вступления ---
class ContractJoinButton(Button):
    # ... код ...

# --- Функция завершения контракта ---
async def finish_contract(contract_id: str):
    # ... код ...

# --- Таймер контракта ---
async def contract_timer(contract_id: str):
    # ... код ...

# --- Кнопки машин ---
class CarButtonsView(View):
    # ... код ...

# --- Кнопки освобождения ---
class FreeButtonsView(View):
    # ... код ...

# --- СОБЫТИЕ on_ready ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    
    # Проверяем каналы
    for channel_id, name in [(CONTRACT_CHANNEL_ID, "Контрактов"), (CAR_CHANNEL_ID, "Машин")]:
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel:
                print(f'✅ Канал {name} найден: {channel.name}')
            else:
                print(f'❌ КАНАЛ {name} (ID: {channel_id}) НЕ НАЙДЕН!')
    
    # Синхронизация
    try:
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        print(f'✅ Команды синхронизированы')
        
        commands = await tree.fetch_commands(guild=guild)
        print(f'📋 Доступные команды: {[cmd.name for cmd in commands]}')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')
    
    # Очистка и запуск
    if CAR_CHANNEL_ID:
        await update_cars_channel()
    
    await send_log(f"✅ Бот **{client.user}** запущен!")

# --- КОМАНДА: /contr ---
@tree.command(
    name="contr", 
    description="Создать новый контракт",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(name="Название контракта")
async def contr_command(interaction: discord.Interaction, name: str):
    """Создает новый контракт в канале."""
    
    try:
        await interaction.response.defer(thinking=True)
        print(f"✅ /contr от {interaction.user.display_name}: {name}")
        
        if interaction.channel_id != CONTRACT_CHANNEL_ID:
            await interaction.followup.send(
                f"❌ Эта команда доступна только в канале <#{CONTRACT_CHANNEL_ID}>!",
                ephemeral=True
            )
            return
        
        contract_id = f"{interaction.user.id}_{datetime.datetime.now().timestamp()}"
        
        contracts[contract_id] = {
            "name": name,
            "author": interaction.user.display_name,
            "author_id": str(interaction.user.id),
            "members": {},
            "created_at": datetime.datetime.now()
        }
        
        view = View(timeout=None)
        view.add_item(ContractJoinButton(contract_id))
        
        embed = discord.Embed(
            title="📋 Новый контракт",
            description=f"**{name}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Создал", value=interaction.user.mention, inline=True)
        embed.add_field(name="Статус", value="⏳ Набор (0/3)", inline=True)
        embed.add_field(name="Время", value="5 минут", inline=True)
        embed.add_field(name="Минимум", value="2 человека", inline=True)
        embed.add_field(name="Требования", value="Навыки: слабые, средние, сильные", inline=False)
        embed.set_footer(text="Нажмите кнопку ниже, чтобы записаться")
        
        channel = client.get_channel(CONTRACT_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send(
                f"❌ Канал не найден!",
                ephemeral=True
            )
            return
        
        msg = await channel.send(content="@Контракт", embed=embed, view=view)
        await cleanup_channel(CONTRACT_CHANNEL_ID, keep_last=10, exclude_ids=[msg.id])
        
        task = asyncio.create_task(contract_timer(contract_id))
        contracts[contract_id]["timer_task"] = task
        
        await interaction.followup.send(
            f"✅ Контракт **{name}** успешно создан!",
            ephemeral=True
        )
        
    except Exception as e:
        print(f"❌ Ошибка в /contr: {e}")
        import traceback
        traceback.print_exc()
        try:
            await interaction.followup.send(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )
        except:
            pass

# --- КОМАНДА: /cars ---
@tree.command(
    name="cars", 
    description="Обновить список машин",
    guild=discord.Object(id=GUILD_ID)
)
async def cars_command(interaction: discord.Interaction):
    if interaction.channel_id != CAR_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Команда доступна только в канале <#{CAR_CHANNEL_ID}>!",
            ephemeral=True
        )
        return
    
    await interaction.response.send_message("🔄 Обновляю список машин...", ephemeral=True)
    await update_cars_channel()

# --- КОМАНДА: /add_car ---
@tree.command(
    name="add_car", 
    description="Добавить новую машину",
    guild=discord.Object(id=GUILD_ID)
)
async def add_car_command(interaction: discord.Interaction):
    class AddCarModal(Modal):
        def __init__(self):
            super().__init__(title="Добавить машину")
            
            self.car_name_input = TextInput(
                label="Название машины",
                placeholder="Введите название новой машины",
                min_length=1,
                max_length=100,
                required=True
            )
            self.add_item(self.car_name_input)
        
        async def on_submit(self, interaction: discord.Interaction):
            car_name = self.car_name_input.value
            
            if car_name in cars:
                await interaction.response.send_message(
                    f"❌ Машина '{car_name}' уже существует!",
                    ephemeral=True
                )
                return
            
            cars[car_name] = {"status": "Свободна", "user": None, "end_time": None}
            
            await send_log(f"➕ **{interaction.user.display_name}** добавил машину: **{car_name}**")
            
            await interaction.response.send_message(
                f"✅ Машина '{car_name}' успешно добавлена!",
                ephemeral=False
            )
            
            await update_cars_channel()
    
    await interaction.response.send_modal(AddCarModal())

# --- КОМАНДА: /remove_car ---
@tree.command(
    name="remove_car", 
    description="Удалить машину",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(car_name="Название машины для удаления")
async def remove_car_command(interaction: discord.Interaction, car_name: str):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена!",
            ephemeral=True
        )
        return
    
    if cars[car_name]["status"] == "Занята":
        await interaction.response.send_message(
            f"❌ Нельзя удалить машину '{car_name}' — она занята!",
            ephemeral=True
        )
        return
    
    del cars[car_name]
    
    await send_log(f"❌ **{interaction.user.display_name}** удалил машину: **{car_name}**")
    
    await interaction.response.send_message(
        f"✅ Машина '{car_name}' успешно удалена!",
        ephemeral=False
    )
    
    await update_cars_channel()

# --- КОМАНДА: /rename_car ---
@tree.command(
    name="rename_car", 
    description="Переименовать машину",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(car_name="Название машины для переименования")
async def rename_car_command(interaction: discord.Interaction, car_name: str):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена!",
            ephemeral=True
        )
        return
    
    class RenameCarModal(Modal):
        def __init__(self, old_name: str):
            super().__init__(title=f"Переименовать: {old_name}")
            self.old_name = old_name
            
            self.new_name_input = TextInput(
                label="Новое название",
                placeholder="Введите новое название машины",
                min_length=1,
                max_length=100,
                required=True
            )
            self.add_item(self.new_name_input)
        
        async def on_submit(self, interaction: discord.Interaction):
            new_name = self.new_name_input.value
            
            if new_name in cars:
                await interaction.response.send_message(
                    f"❌ Машина '{new_name}' уже существует!",
                    ephemeral=True
                )
                return
            
            car_data = cars.pop(self.old_name)
            cars[new_name] = car_data
            
            await send_log(f"✏️ **{interaction.user.display_name}** переименовал машину: **{self.old_name}** → **{new_name}**")
            
            await interaction.response.send_message(
                f"✅ Машина '{self.old_name}' переименована в '{new_name}'!",
                ephemeral=False
            )
            
            await update_cars_channel()
    
    await interaction.response.send_modal(RenameCarModal(car_name))

# --- КОМАНДА: /list_cars ---
@tree.command(
    name="list_cars", 
    description="Показать список машин без кнопок",
    guild=discord.Object(id=GUILD_ID)
)
async def list_cars_command(interaction: discord.Interaction):
    car_list = generate_car_list()
    await interaction.response.send_message(car_list, ephemeral=True)

# --- КОМАНДА: /take ---
@tree.command(
    name="take", 
    description="Взять машину",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    car_name="Название машины",
    minutes="Время в минутах (от 1 до 120)"
)
async def take_command(
    interaction: discord.Interaction, 
    car_name: str, 
    minutes: app_commands.Range[int, 1, 120]
):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена.",
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

    asyncio.create_task(auto_free_timer(car_name, minutes))

    await interaction.response.send_message(
        f"✅ Машина '{car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
        ephemeral=False
    )
    
    await update_cars_channel()

# --- КОМАНДА: /free ---
@tree.command(
    name="free", 
    description="Освободить машину",
    guild=discord.Object(id=GUILD_ID)
)
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

    if cars[car_name]["user"] != interaction.user.display_name:
        await interaction.response.send_message(
            f"❌ Вы не можете освободить эту машину! Ее взял: {cars[car_name]['user']}",
            ephemeral=True
        )
        return

    user_name = cars[car_name]["user"]
    cars[car_name]["status"] = "Свободна"
    cars[car_name]["user"] = None
    cars[car_name]["end_time"] = None

    await interaction.response.send_message(
        f"✅ Машина '{car_name}' освобождена!",
        ephemeral=False
    )
    
    await update_cars_channel()

# --- ЗАПУСК БОТА ---
token = os.getenv('DISCORD_TOKEN')
if token:
    client.run(token)
else:
    print("❌ ОШИБКА: DISCORD_TOKEN не найден в переменных окружения!")