import os
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import datetime
import asyncio
import pytz
import re
import glob
import json

# --- ID из переменных окружения ---
GUILD_ID = int(os.getenv('GUILD_ID', 0))
CONTRACT_CHANNEL_ID = int(os.getenv('CONTRACT_CHANNEL_ID', 0))
CAR_CHANNEL_ID = int(os.getenv('CAR_CHANNEL_ID', 0))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))
GW_CHANNEL_ID = 1544246587918782504  # ID канала для Граффити Вар

# --- ID каналов для VZP ---
VZP_CHANNELS = [
    1523341052680081408,
    1538899458157318165,
    1523341229289640157
]
VZP_CHANNEL_ID = VZP_CHANNELS[0]

# --- Московский часовой пояс ---
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# --- Путь к файлу с данными о машинах ---
CARS_FILE = 'cars_data.json'

# --- Данные для GW оповещений ---
gw_data = {
    "enabled": False,
    "last_notification": None,
    "task": None
}

# --- Время для оповещений GW (часы и минуты начала интервала) ---
# Оповещения в :30 и :35 каждого интервала
GW_TIMES = [
    (8, 30),   # 08:30 и 08:35
    (10, 30),  # 10:30 и 10:35
    (12, 30),  # 12:30 и 12:35
    (14, 30),  # 14:30 и 14:35
    (16, 30),  # 16:30 и 16:35
    (18, 30),  # 18:30 и 18:35
    (20, 30),  # 20:30 и 20:35
    (22, 30),  # 22:30 и 22:35
    (0, 30),   # 00:30 и 00:35
    (2, 30),   # 02:30 и 02:35
    (4, 30),   # 04:30 и 04:35
    (6, 30),   # 06:30 и 06:35
]

# --- Минуты для оповещений в каждом интервале ---
GW_NOTIFICATION_MINUTES = [30, 35]

# --- Функция для загрузки машин из файла ---
def load_cars():
    try:
        with open(CARS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл {CARS_FILE} не найден! Создаю новый...")
        default_cars = {
            "Karin Rebel TS701VCA": {"status": "Свободна", "user": None, "end_time": None},
            "Benefactor Ml63 2010 ST530MFA": {"status": "Свободна", "user": None, "end_time": None},
            "Annis Jook Nizmo RS 2013 JZ738CKY": {"status": "Свободна", "user": None, "end_time": None},
            "Emperor IC-F 2012 BU363YHX": {"status": "Свободна", "user": None, "end_time": None},
            "Benefactor G-series 63 ASG 6x6 LY699IEB": {"status": "Свободна", "user": None, "end_time": None},
            "Vapid Bronzo Predator 2022 GC643UFN": {"status": "Свободна", "user": None, "end_time": None},
            "Karin Thunder 2021 SY108SFL": {"status": "Свободна", "user": None, "end_time": None},
            "Ubermacht 760I J70 2022": {"status": "Свободна", "user": None, "end_time": None}
        }
        save_cars(default_cars)
        return default_cars
    except json.JSONDecodeError:
        print(f"❌ Ошибка чтения {CARS_FILE}! Создаю новый...")
        default_cars = {
            "Karin Rebel TS701VCA": {"status": "Свободна", "user": None, "end_time": None},
            "Benefactor Ml63 2010 ST530MFA": {"status": "Свободна", "user": None, "end_time": None},
            "Annis Jook Nizmo RS 2013 JZ738CKY": {"status": "Свободна", "user": None, "end_time": None},
            "Emperor IC-F 2012 BU363YHX": {"status": "Свободна", "user": None, "end_time": None},
            "Benefactor G-series 63 ASG 6x6 LY699IEB": {"status": "Свободна", "user": None, "end_time": None},
            "Vapid Bronzo Predator 2022 GC643UFN": {"status": "Свободна", "user": None, "end_time": None},
            "Karin Thunder 2021 SY108SFL": {"status": "Свободна", "user": None, "end_time": None},
            "Ubermacht 760I J70 2022": {"status": "Свободна", "user": None, "end_time": None}
        }
        save_cars(default_cars)
        return default_cars

def save_cars(cars_data):
    try:
        with open(CARS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cars_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения {CARS_FILE}: {e}")
        return False

cars = load_cars()

# --- Данные для контрактов ---
contracts = {}

# --- Данные для VZP ---
vzp_data = {
    "members": {},
    "message_id": None,
    "channel_id": VZP_CHANNEL_ID,
    "target_count": 0,
    "is_completed": False,
    "last_reminder_time": None,
    "reminder_task": None,
    "text": "Сбор реакций на ВЗП!",
    "author_id": None,
    "start_time": None,
    "vzp_type": None,
    "vzp_type_label": None
}

# --- НАСТРОЙКА БОТА ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Функция для проверки, нужно ли отправлять оповещение GW ---
def should_send_gw_notification():
    """Проверяет, нужно ли отправить оповещение о Граффити Вар."""
    if not gw_data["enabled"]:
        return False
    
    now = datetime.datetime.now(MOSCOW_TZ)
    current_hour = now.hour
    current_minute = now.minute
    
    # Проверяем, не отправляли ли уже оповещение в эту минуту
    if gw_data["last_notification"]:
        last = gw_data["last_notification"]
        if (last.year == now.year and last.month == now.month and 
            last.day == now.day and last.hour == now.hour and 
            last.minute == now.minute):
            return False
    
    # Проверяем, есть ли интервал с таким часом
    for hour, minute in GW_TIMES:
        if current_hour == hour:
            # Проверяем, является ли текущая минута 30 или 35
            if current_minute in GW_NOTIFICATION_MINUTES:
                return True
    
    return False

# --- Функция для получения интервала ---
def get_gw_interval(now):
    """Возвращает строку с интервалом для оповещения."""
    current_hour = now.hour
    current_minute = now.minute
    
    # Ищем интервал для текущего часа
    for hour, minute in GW_TIMES:
        if current_hour == hour:
            start_minute = minute
            end_minute = minute + 29
            return f"{hour:02d}:{start_minute:02d} — {hour:02d}:{end_minute:02d}"
    
    return None

# --- Функция отправки оповещения GW ---
async def send_gw_notification():
    """Отправляет оповещение о Граффити Вар."""
    if not gw_data["enabled"]:
        return
    
    channel = client.get_channel(GW_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал GW не найден! ID: {GW_CHANNEL_ID}")
        return
    
    now = datetime.datetime.now(MOSCOW_TZ)
    
    # Определяем интервал
    interval = get_gw_interval(now)
    if not interval:
        return
    
    await channel.send(
        f"@everyone\n"
        f"🎨 **Граффити Вар!**\n"
        f"⏰ Время: **{interval}** (по МСК)\n"
        f"🏃 **ВЗЯЛИ БАЛОНЫ В РУКИ И ВЫЕХАЛИ КРАСИТЬ ГЕТТО!**"
    )
    
    gw_data["last_notification"] = now
    print(f"✅ Оповещение GW отправлено в {now.strftime('%H:%M')}")

# --- Фоновый цикл проверки GW ---
async def gw_loop():
    """Фоновый цикл, проверяющий каждые 10 секунд необходимость отправки оповещения."""
    await client.wait_until_ready()
    
    while not client.is_closed():
        try:
            if gw_data["enabled"] and should_send_gw_notification():
                await send_gw_notification()
        except Exception as e:
            print(f"❌ Ошибка в цикле GW: {e}")
        
        await asyncio.sleep(10)  # Проверяем каждые 10 секунд

# --- Получение списка карт из папки vzp_maps ---
def get_vzp_maps():
    maps = []
    possible_paths = [
        'vzp_maps',
        './vzp_maps',
        '../vzp_maps',
        os.path.join(os.path.dirname(__file__), 'vzp_maps'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vzp_maps'),
    ]
    
    found_path = None
    for path in possible_paths:
        if os.path.exists(path) and os.path.isdir(path):
            found_path = path
            break
    
    if not found_path:
        return []
    
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp']
    for ext in image_extensions:
        pattern = os.path.join(found_path, ext)
        for file_path in glob.glob(pattern):
            map_name = os.path.splitext(os.path.basename(file_path))[0]
            maps.append({
                'name': map_name,
                'path': file_path
            })
    
    return maps

# --- Функция для отправки сообщения в лог-канал ---
async def send_log(message: str, embed: discord.Embed = None):
    if LOG_CHANNEL_ID == 0:
        return
    channel = client.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        return
    if embed:
        await channel.send(message, embed=embed)
    else:
        await channel.send(message)

# --- ФУНКЦИЯ ОЧИСТКИ СТАРЫХ СООБЩЕНИЙ ---
async def cleanup_channel(channel_id: int, keep_last: int = 10, exclude_ids: list = None):
    if exclude_ids is None:
        exclude_ids = []
    
    channel = client.get_channel(channel_id)
    if channel is None:
        return
    
    try:
        messages = []
        async for msg in channel.history(limit=50):
            messages.append(msg)
        
        messages_to_delete = []
        for msg in messages:
            if msg.id not in exclude_ids and not msg.pinned:
                messages_to_delete.append(msg)
        
        if len(messages_to_delete) > keep_last:
            messages_to_delete.sort(key=lambda m: m.created_at)
            to_remove = messages_to_delete[:-keep_last]
            
            if to_remove:
                print(f"🗑️ Удаляю {len(to_remove)} старых сообщений")
                for msg in to_remove:
                    try:
                        await msg.delete()
                        await asyncio.sleep(0.3)
                    except:
                        pass
    except Exception as e:
        print(f"⚠️ Ошибка очистки: {e}")

# --- Функция для создания списка машин ---
def generate_car_list():
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

# --- Функция для освобождения машины (автоматически) ---
async def free_car_auto(car_name: str):
    if car_name not in cars:
        return
    if cars[car_name]["status"] == "Свободна":
        return
    
    user_name = cars[car_name]["user"]
    cars[car_name]["status"] = "Свободна"
    cars[car_name]["user"] = None
    cars[car_name]["end_time"] = None
    
    save_cars(cars)
    
    embed = discord.Embed(
        title="⏰ Машина автоматически освобождена",
        description=f"**{car_name}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Кто взял", value=user_name, inline=True)
    embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    
    await send_log(f"⏰ **{user_name}** время вышло, машина **{car_name}** освобождена", embed=embed)
    await update_cars_channel()

# --- Автоматический таймер освобождения ---
async def auto_free_timer(car_name: str, minutes: int):
    await asyncio.sleep(minutes * 60)
    if car_name in cars and cars[car_name]["status"] == "Занята":
        await free_car_auto(car_name)

# --- Обновление канала с машинами ---
async def update_cars_channel():
    if CAR_CHANNEL_ID == 0:
        return
    
    car_list = generate_car_list()
    
    view = View(timeout=None)
    
    take_view = CarButtonsView()
    for item in take_view.children:
        view.add_item(item)
    
    free_view = FreeButtonsView()
    for item in free_view.children:
        view.add_item(item)
    
    channel = client.get_channel(CAR_CHANNEL_ID)
    if channel:
        msg = await channel.send(
            f"{car_list}\n\n**Кнопки:**\n🟢 Левая колонка - взять машину\n🔴 Правая колонка - освободить машину",
            view=view
        )
        await cleanup_channel(CAR_CHANNEL_ID, keep_last=10, exclude_ids=[msg.id])

# --- Модальное окно для ручного ввода времени ---
class TimeInputModal(Modal):
    def __init__(self, car_name: str):
        super().__init__(title=f"Взять машину: {car_name}")
        self.car_name = car_name
        
        self.time_input = TextInput(
            label="Время в минутах (1-120)",
            placeholder="Введите число от 1 до 120",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.time_input.value)
            
            if minutes < 1 or minutes > 120:
                await interaction.response.send_message(
                    "❌ Время должно быть от 1 до 120 минут!",
                    ephemeral=True
                )
                return
            
            if self.car_name not in cars:
                await interaction.response.send_message(
                    f"❌ Машина '{self.car_name}' не найдена!",
                    ephemeral=True
                )
                return
            
            if cars[self.car_name]["status"] == "Занята":
                await interaction.response.send_message(
                    f"❌ Машина '{self.car_name}' уже занята!",
                    ephemeral=True
                )
                return
            
            user_name = interaction.user.display_name
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            cars[self.car_name]["status"] = "Занята"
            cars[self.car_name]["user"] = user_name
            cars[self.car_name]["end_time"] = end_time
            
            save_cars(cars)
            
            asyncio.create_task(auto_free_timer(self.car_name, minutes))
            
            await interaction.response.send_message(
                f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
                ephemeral=False
            )
            
            await update_cars_channel()
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Введите число!",
                ephemeral=True
            )

# --- Класс для кнопок времени ---
class TimeButtonsView(View):
    def __init__(self, car_name: str):
        super().__init__(timeout=60)
        self.car_name = car_name
    
    @discord.ui.button(label="15 мин", style=discord.ButtonStyle.primary)
    async def time_15(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 15)
    
    @discord.ui.button(label="30 мин", style=discord.ButtonStyle.primary)
    async def time_30(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 30)
    
    @discord.ui.button(label="45 мин", style=discord.ButtonStyle.primary)
    async def time_45(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 45)
    
    @discord.ui.button(label="60 мин", style=discord.ButtonStyle.primary)
    async def time_60(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 60)
    
    @discord.ui.button(label="90 мин", style=discord.ButtonStyle.primary)
    async def time_90(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 90)
    
    @discord.ui.button(label="120 мин", style=discord.ButtonStyle.primary)
    async def time_120(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 120)
    
    @discord.ui.button(label="✏️ Своё время", style=discord.ButtonStyle.secondary)
    async def custom_time(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TimeInputModal(self.car_name))
    
    async def take_car(self, interaction: discord.Interaction, minutes: int):
        if self.car_name not in cars:
            await interaction.response.send_message(
                f"❌ Машина '{self.car_name}' не найдена!",
                ephemeral=True
            )
            return
        
        if cars[self.car_name]["status"] == "Занята":
            await interaction.response.send_message(
                f"❌ Машина '{self.car_name}' уже занята!",
                ephemeral=True
            )
            return
        
        if minutes < 1 or minutes > 120:
            await interaction.response.send_message(
                "❌ Время должно быть от 1 до 120 минут!",
                ephemeral=True
            )
            return
        
        user_name = interaction.user.display_name
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        
        cars[self.car_name]["status"] = "Занята"
        cars[self.car_name]["user"] = user_name
        cars[self.car_name]["end_time"] = end_time
        
        save_cars(cars)
        
        asyncio.create_task(auto_free_timer(self.car_name, minutes))
        
        await interaction.response.send_message(
            f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
            ephemeral=False
        )
        
        await update_cars_channel()

# --- Модальное окно для добавления машины ---
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
        car_name = self.car_name_input.value.strip()
        
        if not car_name:
            await interaction.response.send_message(
                "❌ Название машины не может быть пустым!",
                ephemeral=True
            )
            return
        
        if car_name in cars:
            await interaction.response.send_message(
                f"❌ Машина '{car_name}' уже существует!",
                ephemeral=True
            )
            return
        
        cars[car_name] = {"status": "Свободна", "user": None, "end_time": None}
        
        save_cars(cars)
        
        await send_log(f"➕ **{interaction.user.display_name}** добавил машину: **{car_name}**")
        
        await interaction.response.send_message(
            f"✅ Машина '{car_name}' успешно добавлена!",
            ephemeral=False
        )
        
        await update_cars_channel()

# --- Модальное окно для VZP (текст и количество) ---
class VZPTextModal(Modal):
    def __init__(self):
        super().__init__(title="Создать сбор на ВЗП")
        
        self.vzp_text = TextInput(
            label="Текст сбора",
            placeholder="Введите текст для сбора",
            default="Сбор реакций на ВЗП!",
            required=True,
            max_length=200
        )
        self.add_item(self.vzp_text)
        
        self.vzp_count = TextInput(
            label="Максимальное количество участников",
            placeholder="Введите число (например: 10)",
            default="10",
            required=True,
            max_length=3
        )
        self.add_item(self.vzp_count)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.vzp_count.value)
            if count < 1 or count > 50:
                await interaction.response.send_message(
                    "❌ Количество участников должно быть от 1 до 50!",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Введите число!",
                ephemeral=True
            )
            return
        
        if vzp_data["vzp_type"] is None:
            await interaction.response.send_message(
                "❌ Сначала выберите тип сбора (Атака/Защита)!",
                ephemeral=True
            )
            return
        
        vzp_data["members"] = {}
        vzp_data["target_count"] = count
        vzp_data["is_completed"] = False
        vzp_data["text"] = self.vzp_text.value
        vzp_data["author_id"] = interaction.user.id
        vzp_data["start_time"] = datetime.datetime.now()
        vzp_data["last_reminder_time"] = None
        
        type_emoji = "⚔️" if vzp_data["vzp_type"] == "attack" else "🛡️"
        type_name = "Атака" if vzp_data["vzp_type"] == "attack" else "Защита"
        
        await interaction.response.send_message(
            f"✅ Сбор на ВЗП создан!\n"
            f"**Тип:** {type_emoji} {type_name}\n"
            f"**Текст:** {self.vzp_text.value}\n"
            f"**Максимум участников:** {count}",
            ephemeral=True
        )
        
        await update_vzp_message()
        
        task = asyncio.create_task(vzp_timer())
        vzp_data["reminder_task"] = task

# --- Кнопки выбора типа ВЗП ---
class VZPTypeView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="⚔️ Атака", style=discord.ButtonStyle.danger, custom_id="vzp_type_attack")
    async def type_attack(self, interaction: discord.Interaction, button: Button):
        vzp_data["vzp_type"] = "attack"
        vzp_data["vzp_type_label"] = "⚔️ Атака"
        await interaction.response.send_modal(VZPTextModal())
    
    @discord.ui.button(label="🛡️ Защита", style=discord.ButtonStyle.primary, custom_id="vzp_type_defense")
    async def type_defense(self, interaction: discord.Interaction, button: Button):
        vzp_data["vzp_type"] = "defense"
        vzp_data["vzp_type_label"] = "🛡️ Защита"
        await interaction.response.send_modal(VZPTextModal())

# --- Кнопка "Записаться на ВЗП" ---
class VZPJoinButton(Button):
    def __init__(self):
        super().__init__(
            label="✅ Записаться на ВЗП",
            style=discord.ButtonStyle.success,
            custom_id="vzp_join"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"]:
            await interaction.response.send_message(
                "❌ Сбор уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id in vzp_data["members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны!",
                ephemeral=True
            )
            return
        
        if len(vzp_data["members"]) >= vzp_data["target_count"]:
            await interaction.response.send_message(
                f"❌ Достигнут максимум участников ({vzp_data['target_count']})!",
                ephemeral=True
            )
            return
        
        vzp_data["members"][user_id] = {
            "name": interaction.user.display_name,
            "approved": None
        }
        
        await interaction.response.send_message(
            f"✅ Вы записались на ВЗП!",
            ephemeral=True
        )
        
        await update_vzp_message()

# --- Кнопка "Отписаться от ВЗП" ---
class VZPLeaveButton(Button):
    def __init__(self):
        super().__init__(
            label="❌ Отписаться от ВЗП",
            style=discord.ButtonStyle.danger,
            custom_id="vzp_leave"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"]:
            await interaction.response.send_message(
                "❌ Сбор уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id not in vzp_data["members"]:
            await interaction.response.send_message(
                "❌ Вы не записаны!",
                ephemeral=True
            )
            return
        
        del vzp_data["members"][user_id]
        
        await interaction.response.send_message(
            f"❌ Вы отписались от ВЗП!",
            ephemeral=True
        )
        
        await update_vzp_message()

# --- Кнопка "✅" для подтверждения участника ---
class VZPApproveButton(Button):
    def __init__(self, user_id: str, user_name: str):
        super().__init__(
            label=f"✅ {user_name}",
            style=discord.ButtonStyle.success,
            custom_id=f"vzp_approve_{user_id}"
        )
        self.user_id = user_id
        self.user_name = user_name
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != vzp_data["author_id"]:
            await interaction.response.send_message(
                "❌ Только создатель сбора может подтверждать участников!",
                ephemeral=True
            )
            return
        
        if vzp_data["is_completed"]:
            await interaction.response.send_message(
                "❌ Сбор уже завершен!",
                ephemeral=True
            )
            return
        
        if self.user_id not in vzp_data["members"]:
            await interaction.response.send_message(
                "❌ Участник не найден!",
                ephemeral=True
            )
            return
        
        vzp_data["members"][self.user_id]["approved"] = True
        
        await interaction.response.send_message(
            f"✅ {self.user_name} подтвержден!",
            ephemeral=True
        )
        
        await update_vzp_message()

# --- Кнопка "❌" для отклонения участника ---
class VZPRejectButton(Button):
    def __init__(self, user_id: str, user_name: str):
        super().__init__(
            label=f"❌ {user_name}",
            style=discord.ButtonStyle.danger,
            custom_id=f"vzp_reject_{user_id}"
        )
        self.user_id = user_id
        self.user_name = user_name
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != vzp_data["author_id"]:
            await interaction.response.send_message(
                "❌ Только создатель сбора может отклонять участников!",
                ephemeral=True
            )
            return
        
        if vzp_data["is_completed"]:
            await interaction.response.send_message(
                "❌ Сбор уже завершен!",
                ephemeral=True
            )
            return
        
        if self.user_id not in vzp_data["members"]:
            await interaction.response.send_message(
                "❌ Участник не найден!",
                ephemeral=True
            )
            return
        
        vzp_data["members"][self.user_id]["approved"] = False
        
        await interaction.response.send_message(
            f"❌ {self.user_name} отклонен!",
            ephemeral=True
        )
        
        await update_vzp_message()

# --- Обновление сообщения VZP ---
async def update_vzp_message():
    channel = client.get_channel(vzp_data["channel_id"])
    if channel is None:
        channel = client.get_channel(VZP_CHANNELS[0])
        if channel is None:
            print(f"❌ Канал VZP не найден!")
            return
    
    pending_list = []
    approved_list = []
    rejected_list = []
    
    for user_id, data in vzp_data["members"].items():
        if data["approved"] is True:
            approved_list.append(data['name'])
        elif data["approved"] is False:
            rejected_list.append(data['name'])
        else:
            pending_list.append(data['name'])
    
    time_left = ""
    if vzp_data["start_time"]:
        elapsed = (datetime.datetime.now() - vzp_data["start_time"]).total_seconds()
        remaining = max(0, 600 - elapsed)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        if remaining > 0:
            time_left = f"⏰ Осталось: {minutes} мин {seconds} сек"
        else:
            time_left = "⏰ Время вышло!"
    
    type_emoji = "⚔️" if vzp_data["vzp_type"] == "attack" else "🛡️"
    
    embed = discord.Embed(
        title=f"{type_emoji} Сбор на ВЗП",
        description=f"**{vzp_data['text']}**",
        color=discord.Color.blue()
    )
    embed.add_field(
        name=f"📊 Статус",
        value=f"Участников: {len(vzp_data['members'])}/{vzp_data['target_count']}\n{time_left}",
        inline=False
    )
    
    if pending_list:
        embed.add_field(
            name="⏳ Ожидают подтверждения",
            value="\n".join([f"• {name}" for name in pending_list]),
            inline=False
        )
    
    if approved_list:
        embed.add_field(
            name="✅ Подтверждены",
            value="\n".join([f"• {name}" for name in approved_list]),
            inline=False
        )
    
    if rejected_list:
        embed.add_field(
            name="❌ Отклонены",
            value="\n".join([f"• {name}" for name in rejected_list]),
            inline=False
        )
    
    embed.set_footer(text="Нажмите кнопку, чтобы записаться или отписаться")
    
    view = View(timeout=None)
    view.add_item(VZPJoinButton())
    view.add_item(VZPLeaveButton())
    
    if vzp_data["author_id"] and len(vzp_data["members"]) > 0:
        for user_id, data in vzp_data["members"].items():
            if data["approved"] is None:
                view.add_item(VZPApproveButton(user_id, data['name']))
                view.add_item(VZPRejectButton(user_id, data['name']))
    
    if vzp_data["message_id"]:
        try:
            msg = await channel.fetch_message(vzp_data["message_id"])
            await msg.edit(content="@everyone", embed=embed, view=view)
            return
        except:
            vzp_data["message_id"] = None
    
    msg = await channel.send(content="@everyone", embed=embed, view=view)
    vzp_data["message_id"] = msg.id
    vzp_data["channel_id"] = channel.id

# --- Таймер VZP ---
async def vzp_timer():
    notification_times = [150, 300, 450]
    
    for i, time in enumerate(notification_times):
        await asyncio.sleep(time - (notification_times[i-1] if i > 0 else 0))
        
        if vzp_data["is_completed"]:
            return
        
        channel = client.get_channel(vzp_data["channel_id"])
        if channel:
            remaining = 600 - (datetime.datetime.now() - vzp_data["start_time"]).total_seconds()
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            
            await channel.send(
                f"@everyone\n"
                f"⏰ **Скорее поставьте реакцию на ВЗП!**\n"
                f"Осталось: {minutes} мин {seconds} сек\n"
                f"Участников: {len(vzp_data['members'])}/{vzp_data['target_count']}"
            )
    
    await asyncio.sleep(600 - 450)
    
    if vzp_data["is_completed"]:
        return
    
    await finish_vzp(False)

# --- Завершение сбора VZP ---
async def finish_vzp(success: bool):
    if vzp_data["is_completed"]:
        return
    
    vzp_data["is_completed"] = True
    
    channel = client.get_channel(vzp_data["channel_id"])
    if channel is None:
        return
    
    if vzp_data["message_id"]:
        try:
            msg = await channel.fetch_message(vzp_data["message_id"])
            await msg.delete()
        except:
            pass
    
    type_emoji = "⚔️" if vzp_data["vzp_type"] == "attack" else "🛡️"
    
    if success:
        approved_list = [data['name'] for data in vzp_data["members"].values() if data["approved"] is True]
        
        embed = discord.Embed(
            title=f"{type_emoji} Сбор на ВЗП успешно завершен!",
            description=f"**{vzp_data['text']}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="👥 Идут в теру:",
            value="\n".join([f"• {name}" for name in approved_list]) if approved_list else "🔴 Нет участников",
            inline=False
        )
        embed.set_footer(text="Вперёд парни, принесите Дону победу!")
        
        await channel.send(content="@everyone", embed=embed)
        
    else:
        members_list = [data['name'] for data in vzp_data["members"].values()]
        
        embed = discord.Embed(
            title=f"{type_emoji} Сбор на ВЗП провалился!",
            description=f"**{vzp_data['text']}**\nНедостаточно реакций за 10 минут.",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="📋 Список записавшихся:",
            value="\n".join([f"• {name}" for name in members_list]) if members_list else "🔴 Никто не записался",
            inline=False
        )
        embed.set_footer(text="Попробуйте снова!")
        
        await channel.send(content="@everyone", embed=embed)
    
    vzp_data["members"] = {}
    vzp_data["message_id"] = None
    vzp_data["is_completed"] = False
    vzp_data["target_count"] = 0
    vzp_data["author_id"] = None
    vzp_data["start_time"] = None
    vzp_data["vzp_type"] = None
    vzp_data["vzp_type_label"] = None

# --- Кнопки машин ---
class CarButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        car_list = list(cars.keys())
        for i, car_name in enumerate(car_list):
            label = car_name[:25] + "..." if len(car_name) > 25 else car_name
            button = Button(label=label, style=discord.ButtonStyle.success, custom_id=f"car_{i}")
            button.callback = self.create_callback(car_name)
            self.add_item(button)
    
    def create_callback(self, car_name):
        async def callback(interaction: discord.Interaction):
            if cars[car_name]["status"] == "Занята":
                await interaction.response.send_message(
                    f"❌ Машина **{car_name}** уже занята!",
                    ephemeral=True
                )
                return
            await interaction.response.send_message(
                f"🚗 **{car_name}**\nВыберите время (1-120 мин):",
                view=TimeButtonsView(car_name),
                ephemeral=True
            )
        return callback

# --- Кнопки освобождения ---
class FreeButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        car_list = list(cars.keys())
        for i, car_name in enumerate(car_list):
            label = car_name[:25] + "..." if len(car_name) > 25 else car_name
            button = Button(label=f"🗑️ {label}", style=discord.ButtonStyle.danger, custom_id=f"free_{i}")
            button.callback = self.create_callback(car_name)
            self.add_item(button)
    
    def create_callback(self, car_name):
        async def callback(interaction: discord.Interaction):
            if cars[car_name]["status"] == "Свободна":
                await interaction.response.send_message(
                    f"✅ Машина '{car_name}' уже свободна!",
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
            
            save_cars(cars)
            
            await interaction.response.send_message(
                f"✅ Машина '{car_name}' освобождена!",
                ephemeral=False
            )
            
            await update_cars_channel()
        return callback

# --- Класс для кнопок карт VZP ---
class VZPMapButton(Button):
    def __init__(self, map_name: str, file_path: str):
        super().__init__(
            label=map_name,
            style=discord.ButtonStyle.primary,
            custom_id=f"vzp_map_{map_name}"
        )
        self.map_name = map_name
        self.file_path = file_path
    
    async def callback(self, interaction: discord.Interaction):
        try:
            with open(self.file_path, 'rb') as f:
                file = discord.File(f, filename=f"{self.map_name}.png")
                
                embed = discord.Embed(
                    title=f"🗺️ Карта: {self.map_name}",
                    color=discord.Color.blue()
                )
                embed.set_image(url=f"attachment://{self.map_name}.png")
                embed.set_footer(text="VZP Карта")
                
                await interaction.response.send_message(
                    content=f"🗺️ **Карта {self.map_name}**",
                    embed=embed,
                    file=file,
                    ephemeral=True
                )
        except Exception as e:
            print(f"❌ Ошибка при отправке карты {self.map_name}: {e}")
            await interaction.response.send_message(
                f"❌ Не удалось загрузить карту {self.map_name}",
                ephemeral=True
            )

# --- Вью для кнопок карт VZP ---
class VZPMapsView(View):
    def __init__(self, maps: list):
        super().__init__(timeout=None)
        for map_data in maps:
            self.add_item(VZPMapButton(map_data['name'], map_data['path']))

# --- Функция для создания контракта из сообщения ---
async def create_contract_from_message(message: discord.Message, name: str):
    print(f"🔵 Создание контракта из сообщения от {message.author.display_name}")
    print(f"🔵 Название: {name}")
    
    channel = message.channel
    
    contract_id = f"{message.author.id}_{int(datetime.datetime.now().timestamp())}"
    
    contracts[contract_id] = {
        "name": name,
        "author": message.author.display_name,
        "author_id": str(message.author.id),
        "members": {},
        "created_at": datetime.datetime.now(),
        "message_id": None,
        "time_left": "10 минут"
    }
    
    print(f"✅ Контракт создан: {contract_id}")
    
    embed = discord.Embed(
        title="📋 Контракт",
        description=f"**{name}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Создал", value=message.author.mention, inline=True)
    embed.add_field(name="Статус", value="⏳ Набор участников (0/3)", inline=True)
    embed.add_field(name="Осталось времени", value="10 минут", inline=True)
    embed.add_field(name="Минимум", value="2 человека", inline=True)
    embed.add_field(name="👥 Участники (0 человек)", value="🔴 Нет участников", inline=False)
    embed.set_footer(text="Нажмите кнопку ниже, чтобы записаться")
    
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    
    try:
        sent_message = await channel.send(
            content="@Контракт @everyone",
            embed=embed,
            view=view
        )
        contracts[contract_id]["message_id"] = sent_message.id
        print(f"✅ Сообщение отправлено: {sent_message.id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")
        if contract_id in contracts:
            del contracts[contract_id]
        return
    
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    view.add_item(CancelContractButton(contract_id))
    await sent_message.edit(view=view)
    
    try:
        task = asyncio.create_task(contract_timer(contract_id))
        contracts[contract_id]["timer_task"] = task
        print(f"✅ Таймер запущен с 0")
    except Exception as e:
        print(f"❌ Ошибка при запуске таймера: {e}")

# --- Функция для обновления сообщения с контрактом ---
async def update_contract_message(contract_id: str):
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    member_list = "\n".join([f"• {data['name']} - {data['skill']}" for data in members.values()]) if members else "🔴 Нет участников"
    
    embed = discord.Embed(
        title="📋 Контракт",
        description=f"**{contract_data['name']}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Создал", value=contract_data['author'], inline=True)
    embed.add_field(name="Статус", value=f"⏳ Набор участников ({len(members)}/3)", inline=True)
    embed.add_field(name="Осталось времени", value=contract_data['time_left'], inline=True)
    embed.add_field(name="Минимум", value="2 человека", inline=True)
    embed.add_field(
        name=f"👥 Участники ({len(members)} человек)",
        value=member_list,
        inline=False
    )
    embed.set_footer(text="Нажмите кнопку ниже, чтобы записаться или отказаться")
    
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    view.add_item(CancelContractButton(contract_id))
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel and "message_id" in contract_data:
        try:
            msg = await channel.fetch_message(contract_data["message_id"])
            await msg.edit(content="@Контракт @everyone", embed=embed, view=view)
        except:
            msg = await channel.send(content="@Контракт @everyone", embed=embed, view=view)
            contract_data["message_id"] = msg.id

# --- Модальное окно с выбором навыков ---
class SkillSelectView(View):
    def __init__(self, contract_id: str):
        super().__init__(timeout=60)
        self.contract_id = contract_id
        
        self.select = Select(
            placeholder="Выберите уровень навыков",
            options=[
                discord.SelectOption(label="🔹 Слабые", value="weak", description="Базовый уровень"),
                discord.SelectOption(label="🔸 Средние", value="medium", description="Средний уровень"),
                discord.SelectOption(label="🔺 Сильные", value="strong", description="Высокий уровень"),
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        skill_level = self.select.values[0]
        
        skill_names = {
            "weak": "🔹 Слабые",
            "medium": "🔸 Средние",
            "strong": "🔺 Сильные"
        }
        skill_text = skill_names.get(skill_level, "Не указаны")
        
        user_id = str(interaction.user.id)
        
        if self.contract_id not in contracts:
            await interaction.response.send_message(
                "❌ Контракт уже завершен!",
                ephemeral=True
            )
            return
        
        if user_id in contracts[self.contract_id]["members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны!",
                ephemeral=True
            )
            return
        
        contracts[self.contract_id]["members"][user_id] = {
            "name": interaction.user.display_name,
            "skill": skill_text
        }
        
        print(f"✅ Участник добавлен: {interaction.user.display_name} ({skill_text})")
        print(f"📊 Всего участников: {len(contracts[self.contract_id]['members'])}")
        
        await update_contract_message(self.contract_id)
        
        await interaction.response.send_message(
            f"✅ Вы записались на контракт с навыками: **{skill_text}**!",
            ephemeral=True
        )
        
        if len(contracts[self.contract_id]["members"]) >= 3:
            await finish_contract(self.contract_id)

# --- Кнопка "Отказаться" ---
class CancelContractButton(Button):
    def __init__(self, contract_id: str):
        super().__init__(
            label="❌ Отказаться от выполнения",
            style=discord.ButtonStyle.danger,
            custom_id=f"cancel_contract_{contract_id}"
        )
        self.contract_id = contract_id
    
    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        if self.contract_id not in contracts:
            await interaction.response.send_message(
                "❌ Контракт уже завершен!",
                ephemeral=True
            )
            return
        
        if user_id not in contracts[self.contract_id]["members"]:
            await interaction.response.send_message(
                "❌ Вы не записаны на этот контракт!",
                ephemeral=True
            )
            return
        
        del contracts[self.contract_id]["members"][user_id]
        
        await update_contract_message(self.contract_id)
        
        await interaction.response.send_message(
            f"❌ Вы отказались от выполнения контракта!",
            ephemeral=True
        )

# --- Кнопка вступления ---
class ContractJoinButton(Button):
    def __init__(self, contract_id: str):
        super().__init__(
            label="✅ Вступить на выполнение контракта",
            style=discord.ButtonStyle.success,
            custom_id=f"contract_join_{contract_id}"
        )
        self.contract_id = contract_id
    
    async def callback(self, interaction: discord.Interaction):
        print(f"🔵 Кнопка нажата пользователем {interaction.user.display_name}")
        
        if self.contract_id not in contracts:
            await interaction.response.send_message(
                "❌ Контракт уже завершен или не существует!",
                ephemeral=True
            )
            return
        
        if str(interaction.user.id) in contracts[self.contract_id]["members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны на этот контракт!",
                ephemeral=True
            )
            return
        
        view = SkillSelectView(self.contract_id)
        
        await interaction.response.send_message(
            "📝 **Выберите уровень ваших навыков:**",
            view=view,
            ephemeral=True
        )

# --- Функция отправки уведомления ---
async def send_contract_notification(contract_id: str, minutes: int, seconds: int = 0):
    if contract_id not in contracts:
        return None
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    if len(members) >= 3:
        return None
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        return None
    
    if seconds > 0:
        time_text = f"{minutes} мин {seconds} сек"
    else:
        time_text = f"{minutes} минут"
    
    needed = 3 - len(members)
    
    msg = await channel.send(
        f"@Контракт @everyone\n"
        f"⏰ **Осталось {time_text}!**\n"
        f"Скорее ставьте реакции в контракт **{contract_data['name']}**!\n"
        f"Нужно еще **{needed}** человек."
    )
    return msg.id

# --- Таймер контракта ---
async def contract_timer(contract_id: str):
    notification_ids = []
    
    await asyncio.sleep(150)
    if contract_id in contracts:
        msg_id = await send_contract_notification(contract_id, 7, 30)
        if msg_id:
            notification_ids.append(msg_id)
    
    await asyncio.sleep(150)
    if contract_id in contracts:
        msg_id = await send_contract_notification(contract_id, 5, 0)
        if msg_id:
            notification_ids.append(msg_id)
    
    await asyncio.sleep(150)
    if contract_id in contracts:
        msg_id = await send_contract_notification(contract_id, 2, 30)
        if msg_id:
            notification_ids.append(msg_id)
    
    await asyncio.sleep(150)
    
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel:
        for msg_id in notification_ids:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass
    
    if len(members) >= 2:
        embed = discord.Embed(
            title="✅ Контракт сформирован!",
            description=f"**{contract_data['name']}**",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Создал", value=contract_data['author'], inline=True)
        
        member_list = []
        for user_id, data in members.items():
            member_list.append(
                f"**{data['name']}**\n"
                f"  📊 Навыки: {data['skill']}"
            )
        
        embed.add_field(
            name=f"👥 Участники ({len(members)} человек)",
            value="\n\n".join(member_list),
            inline=False
        )
        embed.set_footer(text="Удачи в выполнении контракта! 🍀")
        
        if "message_id" in contract_data and contract_data["message_id"]:
            try:
                msg = await channel.fetch_message(contract_data["message_id"])
                await msg.delete()
            except:
                pass
        
        msg = await channel.send(
            content="@Контракт @everyone",
            embed=embed
        )
        await cleanup_channel(CONTRACT_CHANNEL_ID, keep_last=10, exclude_ids=[msg.id])
        
    else:
        member_list = "\n".join([f"• {data['name']}" for data in members.values()]) if members else "🔴 Никто не записался"
        
        if "message_id" in contract_data and contract_data["message_id"]:
            try:
                msg = await channel.fetch_message(contract_data["message_id"])
                await msg.delete()
            except:
                pass
        
        await channel.send(
            f"❌ **Сбор на контракт '{contract_data['name']}' провалился!**\n"
            f"**Создал:** {contract_data['author']}\n"
            f"**Записалось:** {len(members)} человек\n"
            f"**Список записавшихся:**\n{member_list}"
        )
    
    if contract_id in contracts:
        del contracts[contract_id]

# --- Функция завершения контракта ---
async def finish_contract(contract_id: str):
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    if "timer_task" in contract_data:
        contract_data["timer_task"].cancel()
    
    if len(members) < 2:
        channel = client.get_channel(CONTRACT_CHANNEL_ID)
        if channel:
            if "message_id" in contract_data and contract_data["message_id"]:
                try:
                    msg = await channel.fetch_message(contract_data["message_id"])
                    await msg.delete()
                except:
                    pass
            
            await channel.send(
                f"❌ **{contract_data['name']}**\n"
                f"Извините, нужно минимум двое на контракт.\n"
                f"Записалось: {len(members)} человек."
            )
        del contracts[contract_id]
        return
    
    embed = discord.Embed(
        title="✅ Контракт сформирован!",
        description=f"**{contract_data['name']}**",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Создал", value=contract_data['author'], inline=True)
    
    member_list = []
    for user_id, data in members.items():
        member_list.append(
            f"**{data['name']}**\n"
            f"  📊 Навыки: {data['skill']}"
        )
    
    embed.add_field(
        name=f"👥 Участники ({len(members)} человек)",
        value="\n\n".join(member_list),
        inline=False
    )
    embed.set_footer(text="Удачи в выполнении контракта! 🍀")
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel:
        if "message_id" in contract_data and contract_data["message_id"]:
            try:
                msg = await channel.fetch_message(contract_data["message_id"])
                await msg.delete()
            except:
                pass
        
        msg = await channel.send(
            content="@Контракт @everyone",
            embed=embed
        )
        await cleanup_channel(CONTRACT_CHANNEL_ID, keep_last=10, exclude_ids=[msg.id])
    
    del contracts[contract_id]

# --- Обработчик сообщений ---
@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    
    if message.channel.id != CONTRACT_CHANNEL_ID:
        return
    
    content = message.content.strip()
    
    if content.lower().startswith('/contr'):
        text = content[6:].strip()
        if text:
            await create_contract_from_message(message, text)
            try:
                await message.delete()
            except:
                pass
            return
    
    if content.lower().startswith('!контракт'):
        text = content[9:].strip()
        if text:
            await create_contract_from_message(message, text)
            try:
                await message.delete()
            except:
                pass
            return

# --- СОБЫТИЕ on_ready ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    
    print(f"📁 Текущая директория: {os.getcwd()}")
    print(f"📁 Загружено машин: {len(cars)}")
    
    for channel_id in VZP_CHANNELS:
        channel = client.get_channel(channel_id)
        if channel:
            print(f'✅ Канал VZP найден: {channel.name} (ID: {channel.id})')
        else:
            print(f'❌ КАНАЛ VZP (ID: {channel_id}) НЕ НАЙДЕН!')
    
    gw_channel = client.get_channel(GW_CHANNEL_ID)
    if gw_channel:
        print(f'✅ Канал GW найден: {gw_channel.name} (ID: {gw_channel.id})')
    else:
        print(f'❌ КАНАЛ GW (ID: {GW_CHANNEL_ID}) НЕ НАЙДЕН!')
    
    for channel_id, name in [(CONTRACT_CHANNEL_ID, "Контрактов"), (CAR_CHANNEL_ID, "Машин")]:
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel:
                print(f'✅ Канал {name} найден: {channel.name}')
            else:
                print(f'❌ КАНАЛ {name} (ID: {channel_id}) НЕ НАЙДЕН!')
    
    try:
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        print(f'✅ Команды синхронизированы')
        commands = await tree.fetch_commands(guild=guild)
        print(f'📋 Доступные команды: {[cmd.name for cmd in commands]}')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')
    
    if CAR_CHANNEL_ID:
        await update_cars_channel()
    
    # Запускаем фоновый цикл GW
    client.loop.create_task(gw_loop())
    
    await send_log(f"✅ Бот **{client.user}** запущен!")

# --- КОМАНДА: /contr ---
@tree.command(
    name="contr", 
    description="Создать новый контракт",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(name="Название контракта")
async def contr_command(interaction: discord.Interaction, name: str):
    print(f"🔵 Команда /contr вызвана пользователем {interaction.user.display_name}")
    print(f"🔵 Название: {name}")
    print(f"🔵 Канал: {interaction.channel_id}")
    
    if interaction.channel_id != CONTRACT_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эта команда доступна только в канале <#{CONTRACT_CHANNEL_ID}>!",
            ephemeral=True
        )
        return
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        await interaction.response.send_message(
            f"❌ Канал с ID {CONTRACT_CHANNEL_ID} не найден!",
            ephemeral=True
        )
        return
    
    print(f"✅ Канал найден: {channel.name}")
    
    contract_id = f"{interaction.user.id}_{int(datetime.datetime.now().timestamp())}"
    
    contracts[contract_id] = {
        "name": name,
        "author": interaction.user.display_name,
        "author_id": str(interaction.user.id),
        "members": {},
        "created_at": datetime.datetime.now(),
        "message_id": None,
        "time_left": "10 минут"
    }
    
    print(f"✅ Контракт создан: {contract_id}")
    
    embed = discord.Embed(
        title="📋 Контракт",
        description=f"**{name}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Создал", value=interaction.user.mention, inline=True)
    embed.add_field(name="Статус", value="⏳ Набор участников (0/3)", inline=True)
    embed.add_field(name="Осталось времени", value="10 минут", inline=True)
    embed.add_field(name="Минимум", value="2 человека", inline=True)
    embed.add_field(name="👥 Участники (0 человек)", value="🔴 Нет участников", inline=False)
    embed.set_footer(text="Нажмите кнопку ниже, чтобы записаться")
    
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    
    try:
        sent_message = await channel.send(
            content="@Контракт @everyone",
            embed=embed,
            view=view
        )
        contracts[contract_id]["message_id"] = sent_message.id
        print(f"✅ Сообщение отправлено: {sent_message.id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")
        await interaction.response.send_message(
            f"❌ Не удалось отправить сообщение: {e}",
            ephemeral=True
        )
        if contract_id in contracts:
            del contracts[contract_id]
        return
    
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    view.add_item(CancelContractButton(contract_id))
    await sent_message.edit(view=view)
    
    try:
        task = asyncio.create_task(contract_timer(contract_id))
        contracts[contract_id]["timer_task"] = task
        print(f"✅ Таймер запущен с 0")
    except Exception as e:
        print(f"❌ Ошибка при запуске таймера: {e}")
    
    try:
        await interaction.response.send_message(
            f"✅ Контракт **{name}** успешно создан!",
            ephemeral=True
        )
        print(f"✅ Ответ отправлен пользователю")
    except Exception as e:
        print(f"❌ Ошибка при ответе пользователю: {e}")

# --- КОМАНДА: /vzpgo ---
@tree.command(
    name="vzpgo", 
    description="Создать сбор на ВЗП",
    guild=discord.Object(id=GUILD_ID)
)
async def vzpgo_command(interaction: discord.Interaction):
    if interaction.channel_id not in VZP_CHANNELS:
        channels_mentions = " ".join([f"<#{ch_id}>" for ch_id in VZP_CHANNELS])
        await interaction.response.send_message(
            f"❌ Эта команда доступна только в каналах: {channels_mentions}!",
            ephemeral=True
        )
        return
    
    if vzp_data["is_completed"]:
        await interaction.response.send_message(
            "❌ Сбор уже завершен! Дождитесь окончания.",
            ephemeral=True
        )
        return
    
    vzp_data["channel_id"] = interaction.channel_id
    vzp_data["vzp_type"] = None
    vzp_data["vzp_type_label"] = None
    
    embed = discord.Embed(
        title="⚔️ Создание сбора на ВЗП",
        description="**Выберите тип сбора:**\n"
        "⚔️ **Атака** - для наступательных действий\n"
        "🛡️ **Защита** - для оборонительных действий",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Выберите тип, затем введите текст и количество участников")
    
    view = VZPTypeView()
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- КОМАНДА: /vzp_maps ---
@tree.command(
    name="vzp_maps", 
    description="Показать все карты VZP",
    guild=discord.Object(id=GUILD_ID)
)
async def vzp_maps_command(interaction: discord.Interaction):
    maps = get_vzp_maps()
    
    if not maps:
        await interaction.response.send_message(
            "❌ **Карты не найдены!**\n"
            "Убедитесь, что папка `vzp_maps` существует и содержит изображения карт.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🗺️ Карты VZP",
        description=f"**Найдено карт: {len(maps)}**\n\n"
        "Нажмите на кнопку с названием карты, чтобы увидеть её.",
        color=discord.Color.blue()
    )
    
    map_names = "\n".join([f"• {m['name']}" for m in maps])
    embed.add_field(
        name="📋 Список карт:",
        value=map_names if map_names else "Нет карт",
        inline=False
    )
    embed.set_footer(text="Нажмите на кнопку ниже, чтобы посмотреть карту")
    
    view = VZPMapsView(maps)
    
    await interaction.response.send_message(embed=embed, view=view)

# --- КОМАНДА: /gw_on ---
@tree.command(
    name="gw_on", 
    description="Включить оповещения о Граффити Вар",
    guild=discord.Object(id=GUILD_ID)
)
async def gw_on_command(interaction: discord.Interaction):
    """Включает оповещения о Граффити Вар."""
    
    if gw_data["enabled"]:
        await interaction.response.send_message(
            "🔔 **Оповещения о Граффити Вар уже включены!**",
            ephemeral=True
        )
        return
    
    gw_data["enabled"] = True
    gw_data["last_notification"] = None
    
    await interaction.response.send_message(
        "🔔 **Оповещения о Граффити Вар включены!**\n"
        f"📢 Канал: <#{GW_CHANNEL_ID}>\n"
        f"⏰ Оповещения в :30 и :35 каждого часа:\n"
        f"08:30, 08:35, 10:30, 10:35, 12:30, 12:35, 14:30, 14:35,\n"
        f"16:30, 16:35, 18:30, 18:35, 20:30, 20:35, 22:30, 22:35,\n"
        f"00:30, 00:35, 02:30, 02:35, 04:30, 04:35, 06:30, 06:35 (МСК)\n\n"
        f"Чтобы отключить, используйте `/gw_off`",
        ephemeral=True
    )

# --- КОМАНДА: /gw_off ---
@tree.command(
    name="gw_off", 
    description="Отключить оповещения о Граффити Вар",
    guild=discord.Object(id=GUILD_ID)
)
async def gw_off_command(interaction: discord.Interaction):
    """Отключает оповещения о Граффити Вар."""
    
    if not gw_data["enabled"]:
        await interaction.response.send_message(
            "🔕 **Оповещения о Граффити Вар уже отключены!**",
            ephemeral=True
        )
        return
    
    gw_data["enabled"] = False
    gw_data["last_notification"] = None
    
    await interaction.response.send_message(
        "🔕 **Оповещения о Граффити Вар отключены!**\n"
        "Чтобы включить, используйте `/gw_on`",
        ephemeral=True
    )

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
@app_commands.describe(car_name="Название новой машины")
async def add_car_command(interaction: discord.Interaction, car_name: str):
    car_name = car_name.strip()
    
    if not car_name:
        await interaction.response.send_message(
            "❌ Название машины не может быть пустым!",
            ephemeral=True
        )
        return
    
    if car_name in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' уже существует!",
            ephemeral=True
        )
        return
    
    cars[car_name] = {"status": "Свободна", "user": None, "end_time": None}
    save_cars(cars)
    
    await send_log(f"➕ **{interaction.user.display_name}** добавил машину: **{car_name}**")
    
    await interaction.response.send_message(
        f"✅ Машина '{car_name}' успешно добавлена!",
        ephemeral=False
    )
    
    await update_cars_channel()

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
    save_cars(cars)
    
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
@app_commands.describe(
    old_name="Текущее название машины",
    new_name="Новое название машины"
)
async def rename_car_command(interaction: discord.Interaction, old_name: str, new_name: str):
    old_name = old_name.strip()
    new_name = new_name.strip()
    
    if not old_name or not new_name:
        await interaction.response.send_message(
            "❌ Название не может быть пустым!",
            ephemeral=True
        )
        return
    
    if old_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{old_name}' не найдена!",
            ephemeral=True
        )
        return
    
    if cars[old_name]["status"] == "Занята":
        await interaction.response.send_message(
            f"❌ Нельзя переименовать машину '{old_name}' — она занята!",
            ephemeral=True
        )
        return
    
    if new_name in cars:
        await interaction.response.send_message(
            f"❌ Машина '{new_name}' уже существует!",
            ephemeral=True
        )
        return
    
    car_data = cars.pop(old_name)
    cars[new_name] = car_data
    save_cars(cars)
    
    await send_log(f"✏️ **{interaction.user.display_name}** переименовал машину: **{old_name}** → **{new_name}**")
    
    await interaction.response.send_message(
        f"✅ Машина '{old_name}' переименована в '{new_name}'!",
        ephemeral=False
    )
    
    await update_cars_channel()

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
    
    save_cars(cars)
    
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
    
    save_cars(cars)
    
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