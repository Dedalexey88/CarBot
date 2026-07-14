import os
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import datetime
import asyncio
import pytz

# --- ID из переменных окружения ---
GUILD_ID = int(os.getenv('GUILD_ID', 0))
CONTRACT_CHANNEL_ID = int(os.getenv('CONTRACT_CHANNEL_ID', 0))
CAR_CHANNEL_ID = int(os.getenv('CAR_CHANNEL_ID', 0))
VZP_CHANNEL_ID = 1523341052680081408  # ID канала для VZP
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# --- Московский часовой пояс ---
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# --- Данные о машинах (7 штук) ---
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

# --- Данные для VZP ---
vzp_data = {
    "attack_members": {},
    "defense_members": {},
    "attack_message_id": None,
    "defense_message_id": None,
    "channel_id": VZP_CHANNEL_ID,
    "attack_target": 0,
    "defense_target": 0,
    "attack_text": "",
    "defense_text": "",
    "is_completed": False,
    "last_reminder_time": None,
    "reminder_task": None,
    "attack_completed": False,
    "defense_completed": False
}

# --- НАСТРОЙКА БОТА ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

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
    
    embed = discord.Embed(
        title="⏰ Машина автоматически освобождена",
        description=f"**{car_name}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Кто взял", value=user_name, inline=True)
    embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    
    await send_log(f"⏰ **{user_name}** время вышло, машина **{car_name}** освобождена", embed=embed)
    await update_cars_channel()

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

# --- Автоматический таймер ---
async def auto_free_timer(car_name: str, minutes: int):
    await asyncio.sleep(minutes * 60)
    if car_name in cars and cars[car_name]["status"] == "Занята":
        await free_car_auto(car_name)

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
        
        asyncio.create_task(auto_free_timer(self.car_name, minutes))
        
        await interaction.response.send_message(
            f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
            ephemeral=False
        )
        
        await update_cars_channel()

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
    """Отправляет уведомление о контракте с тегами."""
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    # Проверяем, не завершен ли контракт
    if len(members) >= 3:
        return
    
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        return
    
    # Формируем время
    if seconds > 0:
        time_text = f"{minutes} мин {seconds} сек"
    else:
        time_text = f"{minutes} минут"
    
    needed = 3 - len(members)
    
    await channel.send(
        f"@Контракт @everyone\n"
        f"⏰ **Осталось {time_text}!**\n"
        f"Скорее ставьте реакции в контракт **{contract_data['name']}**!\n"
        f"Нужно еще **{needed}** человек."
    )

# --- Таймер контракта с уведомлениями ---
async def contract_timer(contract_id: str):
    """Таймер для контракта с уведомлениями на 2:30, 5:00 и 7:30."""
    
    # Уведомление через 2 минуты 30 секунд
    await asyncio.sleep(150)  # 2:30
    
    if contract_id in contracts:
        await send_contract_notification(contract_id, 2, 30)
    
    # Уведомление через 5 минут (еще через 2:30)
    await asyncio.sleep(150)  # еще 2:30 (всего 5:00)
    
    if contract_id in contracts:
        await send_contract_notification(contract_id, 5, 0)
    
    # Уведомление через 7 минут 30 секунд (еще через 2:30)
    await asyncio.sleep(150)  # еще 2:30 (всего 7:30)
    
    if contract_id in contracts:
        await send_contract_notification(contract_id, 7, 30)
    
    # Ждем до 10 минут (еще 2:30)
    await asyncio.sleep(150)  # еще 2:30 (всего 10:00)
    
    # Проверяем, существует ли еще контракт
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    
    # Проверяем, собралось ли достаточно участников
    if len(contract_data["members"]) >= 3:
        return
    
    # Контракт провалился - удаляем сообщение и уведомляем
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel:
        # Удаляем сообщение с контрактом
        if "message_id" in contract_data and contract_data["message_id"]:
            try:
                msg = await channel.fetch_message(contract_data["message_id"])
                await msg.delete()
            except:
                pass
        
        # Отправляем сообщение о провале
        await channel.send(
            f"❌ **Сбор на контракт '{contract_data['name']}' провалился!**\n"
            f"Недостаточно реакций. Собрано: {len(contract_data['members'])} из 3 человек."
        )
    
    # Удаляем контракт из памяти
    if contract_id in contracts:
        del contracts[contract_id]

# --- Функция завершения контракта ---
async def finish_contract(contract_id: str):
    if contract_id not in contracts:
        return
    
    contract_data = contracts[contract_id]
    members = contract_data["members"]
    
    # Отменяем таймер, если он есть
    if "timer_task" in contract_data:
        contract_data["timer_task"].cancel()
    
    if len(members) < 2:
        channel = client.get_channel(CONTRACT_CHANNEL_ID)
        if channel:
            # Удаляем сообщение с контрактом
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
    
    # Контракт успешно сформирован - желаем удачи
    embed = discord.Embed(
        title="✅ Контракт сформирован!",
        description=f"**{contract_data['name']}**",
        color=discord.Color.green()
    )
    
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
        # Удаляем старое сообщение с контрактом
        if "message_id" in contract_data and contract_data["message_id"]:
            try:
                msg = await channel.fetch_message(contract_data["message_id"])
                await msg.delete()
            except:
                pass
        
        # Отправляем финальное сообщение
        msg = await channel.send(
            content="@Контракт @everyone",
            embed=embed
        )
        await cleanup_channel(CONTRACT_CHANNEL_ID, keep_last=10, exclude_ids=[msg.id])
    
    del contracts[contract_id]

# --- Кнопки машин ---
class CarButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        car_list = list(cars.keys())
        for i, car_name in enumerate(car_list[:7]):
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
        for i, car_name in enumerate(car_list[:7]):
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
            
            await interaction.response.send_message(
                f"✅ Машина '{car_name}' освобождена!",
                ephemeral=False
            )
            
            await update_cars_channel()
        return callback

# --- Кнопки для VZP ---
class VZPAtkJoinButton(Button):
    def __init__(self):
        super().__init__(
            label="⚔️ Записаться в атаку",
            style=discord.ButtonStyle.success,
            custom_id="vzp_atk_join"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"] or vzp_data["attack_completed"]:
            await interaction.response.send_message(
                "❌ Сбор на атаку уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id in vzp_data["attack_members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны в атаку!",
                ephemeral=True
            )
            return
        
        if user_id in vzp_data["defense_members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны в защиту! Нельзя быть в обеих командах.",
                ephemeral=True
            )
            return
        
        vzp_data["attack_members"][user_id] = {
            "name": interaction.user.display_name
        }
        
        await interaction.response.send_message(
            f"✅ Вы записались в **атаку**!",
            ephemeral=True
        )
        
        await update_vzp_messages()

class VZPAtkLeaveButton(Button):
    def __init__(self):
        super().__init__(
            label="❌ Отписаться из атаки",
            style=discord.ButtonStyle.danger,
            custom_id="vzp_atk_leave"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"] or vzp_data["attack_completed"]:
            await interaction.response.send_message(
                "❌ Сбор на атаку уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id not in vzp_data["attack_members"]:
            await interaction.response.send_message(
                "❌ Вы не записаны в атаку!",
                ephemeral=True
            )
            return
        
        del vzp_data["attack_members"][user_id]
        
        await interaction.response.send_message(
            f"❌ Вы отписались из атаки!",
            ephemeral=True
        )
        
        await update_vzp_messages()

class VZPDefJoinButton(Button):
    def __init__(self):
        super().__init__(
            label="🛡️ Записаться в защиту",
            style=discord.ButtonStyle.success,
            custom_id="vzp_def_join"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"] or vzp_data["defense_completed"]:
            await interaction.response.send_message(
                "❌ Сбор на защиту уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id in vzp_data["defense_members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны в защиту!",
                ephemeral=True
            )
            return
        
        if user_id in vzp_data["attack_members"]:
            await interaction.response.send_message(
                "❌ Вы уже записаны в атаку! Нельзя быть в обеих командах.",
                ephemeral=True
            )
            return
        
        vzp_data["defense_members"][user_id] = {
            "name": interaction.user.display_name
        }
        
        await interaction.response.send_message(
            f"✅ Вы записались в **защиту**!",
            ephemeral=True
        )
        
        await update_vzp_messages()

class VZPDefLeaveButton(Button):
    def __init__(self):
        super().__init__(
            label="❌ Отписаться из защиты",
            style=discord.ButtonStyle.danger,
            custom_id="vzp_def_leave"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if vzp_data["is_completed"] or vzp_data["defense_completed"]:
            await interaction.response.send_message(
                "❌ Сбор на защиту уже завершен!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if user_id not in vzp_data["defense_members"]:
            await interaction.response.send_message(
                "❌ Вы не записаны в защиту!",
                ephemeral=True
            )
            return
        
        del vzp_data["defense_members"][user_id]
        
        await interaction.response.send_message(
            f"❌ Вы отписались из защиты!",
            ephemeral=True
        )
        
        await update_vzp_messages()

# --- Обновление сообщений VZP ---
async def update_vzp_messages():
    channel = client.get_channel(VZP_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал VZP не найден!")
        return
    
    # --- Обновляем сообщение для атаки ---
    if not vzp_data["attack_completed"] and vzp_data["attack_target"] > 0:
        attack_list = "\n".join([f"• {data['name']}" for data in vzp_data["attack_members"].values()]) if vzp_data["attack_members"] else "🔴 Нет участников"
        
        embed_atk = discord.Embed(
            title="⚔️ Сбор на Атаку",
            description=f"**{vzp_data['attack_text']}**" if vzp_data["attack_text"] else "**Сбор на атаку**",
            color=discord.Color.red()
        )
        embed_atk.add_field(
            name=f"👥 Участники ({len(vzp_data['attack_members'])}/{vzp_data['attack_target']})",
            value=attack_list,
            inline=False
        )
        embed_atk.set_footer(text="Нажмите кнопку, чтобы записаться или отписаться")
        
        view_atk = View(timeout=None)
        view_atk.add_item(VZPAtkJoinButton())
        view_atk.add_item(VZPAtkLeaveButton())
        
        if vzp_data["attack_message_id"]:
            try:
                msg = await channel.fetch_message(vzp_data["attack_message_id"])
                await msg.edit(content="@everyone", embed=embed_atk, view=view_atk)
            except:
                msg = await channel.send(content="@everyone", embed=embed_atk, view=view_atk)
                vzp_data["attack_message_id"] = msg.id
        else:
            msg = await channel.send(content="@everyone", embed=embed_atk, view=view_atk)
            vzp_data["attack_message_id"] = msg.id
        
        if len(vzp_data["attack_members"]) >= vzp_data["attack_target"]:
            vzp_data["attack_completed"] = True
            try:
                msg = await channel.fetch_message(vzp_data["attack_message_id"])
                await msg.delete()
                vzp_data["attack_message_id"] = None
            except:
                pass
    
    # --- Обновляем сообщение для защиты ---
    if not vzp_data["defense_completed"] and vzp_data["defense_target"] > 0:
        defense_list = "\n".join([f"• {data['name']}" for data in vzp_data["defense_members"].values()]) if vzp_data["defense_members"] else "🔴 Нет участников"
        
        embed_def = discord.Embed(
            title="🛡️ Сбор на Защиту",
            description=f"**{vzp_data['defense_text']}**" if vzp_data["defense_text"] else "**Сбор на защиту**",
            color=discord.Color.blue()
        )
        embed_def.add_field(
            name=f"👥 Участники ({len(vzp_data['defense_members'])}/{vzp_data['defense_target']})",
            value=defense_list,
            inline=False
        )
        embed_def.set_footer(text="Нажмите кнопку, чтобы записаться или отписаться")
        
        view_def = View(timeout=None)
        view_def.add_item(VZPDefJoinButton())
        view_def.add_item(VZPDefLeaveButton())
        
        if vzp_data["defense_message_id"]:
            try:
                msg = await channel.fetch_message(vzp_data["defense_message_id"])
                await msg.edit(content="@everyone", embed=embed_def, view=view_def)
            except:
                msg = await channel.send(content="@everyone", embed=embed_def, view=view_def)
                vzp_data["defense_message_id"] = msg.id
        else:
            msg = await channel.send(content="@everyone", embed=embed_def, view=view_def)
            vzp_data["defense_message_id"] = msg.id
        
        if len(vzp_data["defense_members"]) >= vzp_data["defense_target"]:
            vzp_data["defense_completed"] = True
            try:
                msg = await channel.fetch_message(vzp_data["defense_message_id"])
                await msg.delete()
                vzp_data["defense_message_id"] = None
            except:
                pass
    
    if vzp_data["attack_completed"] and vzp_data["defense_completed"] and not vzp_data["is_completed"]:
        await complete_vzp()

# --- Завершение сбора VZP ---
async def complete_vzp():
    if vzp_data["is_completed"]:
        return
    
    vzp_data["is_completed"] = True
    
    if vzp_data["reminder_task"]:
        vzp_data["reminder_task"].cancel()
        vzp_data["reminder_task"] = None
    
    attack_list = [data['name'] for data in vzp_data["attack_members"].values()]
    defense_list = [data['name'] for data in vzp_data["defense_members"].values()]
    
    embed = discord.Embed(
        title="⚔️ Реакции собраны!",
        description="**Вперёд парни принесите Дону победу!**",
        color=discord.Color.gold()
    )
    
    attack_text = "\n".join([f"• {name}" for name in attack_list]) if attack_list else "Нет"
    defense_text = "\n".join([f"• {name}" for name in defense_list]) if defense_list else "Нет"
    
    if vzp_data["attack_text"]:
        embed.add_field(
            name=f"⚔️ Атака ({len(attack_list)}/{vzp_data['attack_target']})",
            value=f"Против: {vzp_data['attack_text']}\n{attack_text}",
            inline=True
        )
    else:
        embed.add_field(
            name=f"⚔️ Атака ({len(attack_list)}/{vzp_data['attack_target']})",
            value=attack_text,
            inline=True
        )
    
    if vzp_data["defense_text"]:
        embed.add_field(
            name=f"🛡️ Защита ({len(defense_list)}/{vzp_data['defense_target']})",
            value=f"Против: {vzp_data['defense_text']}\n{defense_text}",
            inline=True
        )
    else:
        embed.add_field(
            name=f"🛡️ Защита ({len(defense_list)}/{vzp_data['defense_target']})",
            value=defense_text,
            inline=True
        )
    
    embed.add_field(
        name=f"👥 Всего участников",
        value=f"{len(attack_list) + len(defense_list)} человек",
        inline=True
    )
    embed.set_footer(text="Удачи! 🎯")
    
    channel = client.get_channel(VZP_CHANNEL_ID)
    if channel:
        await channel.send(content="@everyone", embed=embed)

# --- Функция проверки времени для напоминаний ---
def should_send_reminder():
    now = datetime.datetime.now(MOSCOW_TZ)
    hour = now.hour
    if hour >= 2 and hour < 12:
        return False
    return True

# --- Функция напоминания ---
async def send_reminder():
    channel = client.get_channel(VZP_CHANNEL_ID)
    if channel is None:
        return
    
    if vzp_data["is_completed"]:
        return
    
    if not should_send_reminder():
        return
    
    if vzp_data["last_reminder_time"]:
        time_diff = (datetime.datetime.now() - vzp_data["last_reminder_time"]).total_seconds()
        if time_diff < 7200:
            return
    
    await channel.send(
        "⏰ **Парни прошло 2 часа, как вы не забивали вску, не пора ли собрать и навалять?**\n"
        f"Используйте `/vzp_atk {vzp_data['attack_target']} [текст]` и `/vzp_def {vzp_data['defense_target']} [текст]` для сбора реакций!"
    )
    
    vzp_data["last_reminder_time"] = datetime.datetime.now()

# --- Фоновый цикл напоминаний ---
async def reminder_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if not vzp_data["is_completed"] and (vzp_data["attack_target"] > 0 or vzp_data["defense_target"] > 0):
                await send_reminder()
        except Exception as e:
            print(f"❌ Ошибка в цикле напоминаний: {e}")
        await asyncio.sleep(600)

# --- СОБЫТИЕ on_ready ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    
    for channel_id, name in [(CONTRACT_CHANNEL_ID, "Контрактов"), (CAR_CHANNEL_ID, "Машин"), (VZP_CHANNEL_ID, "VZP")]:
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
    
    vzp_data["attack_members"] = {}
    vzp_data["defense_members"] = {}
    vzp_data["attack_message_id"] = None
    vzp_data["defense_message_id"] = None
    vzp_data["is_completed"] = False
    vzp_data["attack_completed"] = False
    vzp_data["defense_completed"] = False
    vzp_data["last_reminder_time"] = None
    vzp_data["attack_text"] = ""
    vzp_data["defense_text"] = ""
    
    client.loop.create_task(reminder_loop())
    
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
    
    # Запускаем таймер с уведомлениями
    try:
        task = asyncio.create_task(contract_timer(contract_id))
        contracts[contract_id]["timer_task"] = task
        print(f"✅ Таймер запущен")
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

# --- КОМАНДА: /vzp_atk ---
@tree.command(
    name="vzp_atk", 
    description="Создать сбор на атаку",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    count="Количество человек для атаки (например: 6)",
    text="Кто противник (например: skipper)"
)
async def vzp_atk_command(interaction: discord.Interaction, count: app_commands.Range[int, 1, 50], text: str = ""):
    """Создает сбор на атаку в канале VZP."""
    
    print(f"🔵 Команда /vzp_atk вызвана пользователем {interaction.user.display_name}")
    print(f"🔵 Канал: {interaction.channel_id}")
    print(f"🔵 Нужно человек: {count}")
    print(f"🔵 Текст: {text}")
    
    if interaction.channel_id != VZP_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эта команда доступна только в канале <#{VZP_CHANNEL_ID}>!",
            ephemeral=True
        )
        return
    
    if vzp_data["is_completed"]:
        await interaction.response.send_message(
            "❌ Сбор уже завершен! Используйте команду заново.",
            ephemeral=True
        )
        return
    
    vzp_data["attack_target"] = count
    vzp_data["attack_members"] = {}
    vzp_data["attack_message_id"] = None
    vzp_data["attack_completed"] = False
    vzp_data["attack_text"] = text if text else ""
    
    await update_vzp_messages()
    
    if text:
        await interaction.response.send_message(
            f"✅ Сбор на атаку создан! Нужно **{count}** человек против **{text}**.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ Сбор на атаку создан! Нужно **{count}** человек.",
            ephemeral=True
        )

# --- КОМАНДА: /vzp_def ---
@tree.command(
    name="vzp_def", 
    description="Создать сбор на защиту",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    count="Количество человек для защиты (например: 6)",
    text="Кто противник (например: skipper)"
)
async def vzp_def_command(interaction: discord.Interaction, count: app_commands.Range[int, 1, 50], text: str = ""):
    """Создает сбор на защиту в канале VZP."""
    
    print(f"🔵 Команда /vzp_def вызвана пользователем {interaction.user.display_name}")
    print(f"🔵 Канал: {interaction.channel_id}")
    print(f"🔵 Нужно человек: {count}")
    print(f"🔵 Текст: {text}")
    
    if interaction.channel_id != VZP_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эта команда доступна только в канале <#{VZP_CHANNEL_ID}>!",
            ephemeral=True
        )
        return
    
    if vzp_data["is_completed"]:
        await interaction.response.send_message(
            "❌ Сбор уже завершен! Используйте команду заново.",
            ephemeral=True
        )
        return
    
    vzp_data["defense_target"] = count
    vzp_data["defense_members"] = {}
    vzp_data["defense_message_id"] = None
    vzp_data["defense_completed"] = False
    vzp_data["defense_text"] = text if text else ""
    
    await update_vzp_messages()
    
    if text:
        await interaction.response.send_message(
            f"✅ Сбор на защиту создан! Нужно **{count}** человек против **{text}**.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ Сбор на защиту создан! Нужно **{count}** человек.",
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