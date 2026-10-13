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
STREETWARS_CHANNEL_ID = 1544246587918782504  # ID канала для Street Wars
CHR_CHANNEL_ID = 1544246587918782504  # ID канала для Чёрного рынка (можно изменить)

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

# --- Данные для Street Wars ---
streetwars_data = {
    "enabled": False,
    "last_notification": None,
    "task": None
}

# --- Данные для Чёрного рынка ---
chr_data = {
    "enabled": False,
    "last_notification": None,
    "task": None
}

# --- Время для оповещений GW ---
GW_TIMES = [
    (8, 30), (8, 35), (10, 30), (10, 35), (12, 30), (12, 35),
    (14, 30), (14, 35), (16, 30), (16, 35), (18, 30), (18, 35),
    (20, 30), (20, 35), (22, 30), (22, 35), (0, 30), (0, 35),
    (2, 30), (2, 35), (4, 30), (4, 35), (6, 30), (6, 35),
]

# --- Данные для Street Wars ---
STREETWARS_DAYS = {
    0: {"day": "Понедельник", "graffiti": "№11", "file": "11.png"},
    3: {"day": "Четверг", "graffiti": "№38", "file": "38.png"},
    5: {"day": "Суббота", "graffiti": "№46", "file": "46.png"}
}

# --- Время для оповещений Чёрного рынка ---
CHR_TIMES = [(19, 40), (19, 45), (19, 50), (19, 55), (20, 0)]

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
    if not gw_data["enabled"]:
        return False
    
    now = datetime.datetime.now(MOSCOW_TZ)
    current_hour = now.hour
    current_minute = now.minute
    
    if gw_data["last_notification"]:
        last = gw_data["last_notification"]
        if (last.year == now.year and last.month == now.month and 
            last.day == now.day and last.hour == now.hour and 
            last.minute == now.minute):
            return False
    
    for hour, minute in GW_TIMES:
        if current_hour == hour and current_minute == minute:
            return True
    
    return False

# --- Функция для получения интервала GW ---
def get_gw_interval(now):
    current_hour = now.hour
    current_minute = now.minute
    
    if current_minute in [30, 35]:
        return f"{current_hour:02d}:30 — {current_hour:02d}:59"
    return None

# --- Функция отправки оповещения GW ---
async def send_gw_notification():
    if not gw_data["enabled"]:
        return
    
    channel = client.get_channel(GW_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал GW не найден! ID: {GW_CHANNEL_ID}")
        return
    
    now = datetime.datetime.now(MOSCOW_TZ)
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

# --- Функция для проверки Street Wars ---
def should_send_streetwars_notification():
    if not streetwars_data["enabled"]:
        return False
    
    now = datetime.datetime.now(MOSCOW_TZ)
    
    if now.hour != 21 or now.minute != 0:
        return False
    
    if now.weekday() not in STREETWARS_DAYS:
        return False
    
    if streetwars_data["last_notification"]:
        last = streetwars_data["last_notification"]
        if (last.year == now.year and last.month == now.month and 
            last.day == now.day):
            return False
    
    return True

# --- Функция отправки оповещения Street Wars ---
async def send_streetwars_notification():
    if not streetwars_data["enabled"]:
        return
    
    channel = client.get_channel(STREETWARS_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал Street Wars не найден! ID: {STREETWARS_CHANNEL_ID}")
        return
    
    now = datetime.datetime.now(MOSCOW_TZ)
    weekday = now.weekday()
    
    if weekday not in STREETWARS_DAYS:
        return
    
    day_info = STREETWARS_DAYS[weekday]
    
    message = (
        f"@everyone\n"
        f"🏁 **Street Wars!**\n"
        f"📅 День: **{day_info['day']}**\n"
        f"⏰ Время: **21:00 - 21:30** (по МСК)\n"
        f"🎨 Графитка: **{day_info['graffiti']}**\n"
        f"🏃 **Все заряжаемся / групп на мероприятие Street Wars!**"
    )
    
    file_path = os.path.join('graffiti', day_info['file'])
    
    try:
        if os.path.exists(file_path):
            file = discord.File(file_path, filename=day_info['file'])
            await channel.send(message, file=file)
        else:
            await channel.send(message)
            print(f"⚠️ Файл {file_path} не найден!")
    except Exception as e:
        print(f"❌ Ошибка при отправке Street Wars: {e}")
        await channel.send(message)
    
    streetwars_data["last_notification"] = now
    print(f"✅ Оповещение Street Wars отправлено в {now.strftime('%H:%M')}")

# --- Функция для проверки Чёрного рынка ---
def should_send_chr_notification():
    if not chr_data["enabled"]:
        return False
    
    now = datetime.datetime.now(MOSCOW_TZ)
    current_hour = now.hour
    current_minute = now.minute
    
    # Проверяем, не отправляли ли уже в эту минуту
    if chr_data["last_notification"]:
        last = chr_data["last_notification"]
        if (last.year == now.year and last.month == now.month and 
            last.day == now.day and last.hour == now.hour and 
            last.minute == now.minute):
            return False
    
    for hour, minute in CHR_TIMES:
        if current_hour == hour and current_minute == minute:
            return True
    
    return False

# --- Функция отправки оповещения Чёрного рынка ---
async def send_chr_notification():
    if not chr_data["enabled"]:
        return
    
    channel = client.get_channel(CHR_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал Чёрного рынка не найден! ID: {CHR_CHANNEL_ID}")
        return
    
    now = datetime.datetime.now(MOSCOW_TZ)
    
    message = (
        f"@everyone\n"
        f"🖤 **Чёрный рынок!**\n"
        f"⏰ Время: **19:40 - 20:00** (по МСК)\n"
        f"🏃 **Все заряжаемся / групп на мероприятие \"Чёрный рынок\"!**"
    )
    
    file_path = os.path.join('foto', 'blackmarket.png')
    
    try:
        if os.path.exists(file_path):
            file = discord.File(file_path, filename="blackmarket.png")
            await channel.send(message, file=file)
        else:
            await channel.send(message)
            print(f"⚠️ Файл {file_path} не найден!")
    except Exception as e:
        print(f"❌ Ошибка при отправке Чёрного рынка: {e}")
        await channel.send(message)
    
    chr_data["last_notification"] = now
    print(f"✅ Оповещение Чёрного рынка отправлено в {now.strftime('%H:%M')}")

# --- Фоновый цикл проверки ---
async def notification_loop():
    await client.wait_until_ready()
    
    while not client.is_closed():
        try:
            if gw_data["enabled"] and should_send_gw_notification():
                await send_gw_notification()
            
            if streetwars_data["enabled"] and should_send_streetwars_notification():
                await send_streetwars_notification()
            
            if chr_data["enabled"] and should_send_chr_notification():
                await send_chr_notification()
                
        except Exception as e:
            print(f"❌ Ошибка в цикле оповещений: {e}")
        
        await asyncio.sleep(10)

# --- Получение списка карт из папки vzp_maps ---
def get_vzp_maps():
    maps = []
    possible_paths = [
        'vzp_maps', './vzp_maps', '../vzp_maps',
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
            maps.append({'name': map_name, 'path': file_path})
    
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

# --- Функция для освобождения машины ---
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

async def auto_free_timer(car_name: str, minutes: int):
    await asyncio.sleep(minutes * 60)
    if car_name in cars and cars[car_name]["status"] == "Занята":
        await free_car_auto(car_name)

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

# --- Модальное окно для VZP ---
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

# --- Кнопка "✅" ---
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

# --- Кнопка "❌" ---
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
                "❌ Только создатель сбора