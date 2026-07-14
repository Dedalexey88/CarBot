import os
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import datetime
import asyncio

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

# --- ID канала для логов (из переменной окружения) ---
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# --- Настройка бота ---
intents = discord.Intents.default()
intents.message_content = True
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

# --- Функция для освобождения машины ---
async def free_car_auto(car_name: str):
    """Автоматически освобождает машину и отправляет уведомление."""
    if car_name not in cars:
        return
    
    if cars[car_name]["status"] == "Свободна":
        return
    
    user_name = cars[car_name]["user"]
    
    # Освобождаем машину
    cars[car_name]["status"] = "Свободна"
    cars[car_name]["user"] = None
    cars[car_name]["end_time"] = None
    
    # Отправляем уведомление в лог-канал
    embed = discord.Embed(
        title="⏰ Машина автоматически освобождена",
        description=f"**{car_name}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Кто взял", value=user_name, inline=True)
    embed.add_field(name="Причина", value="Время истекло", inline=True)
    embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    
    await send_log(f"⏰ **{user_name}** время вышло, машина **{car_name}** освобождена", embed=embed)

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

# --- Кнопки быстрого выбора времени ---
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
        
        # Запускаем таймер для автоматического освобождения
        asyncio.create_task(auto_free_timer(self.car_name, minutes))
        
        embed = discord.Embed(
            title="🚗 Машина взята",
            description=f"**{self.car_name}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Кто взял", value=user_name, inline=True)
        embed.add_field(name="Время", value=f"{minutes} минут", inline=True)
        embed.add_field(name="До", value=end_time.strftime("%H:%M"), inline=True)
        embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
        
        await send_log(f"✅ **{user_name}** взял машину **{self.car_name}**", embed=embed)
        
        await interaction.response.send_message(
            f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
            ephemeral=False
        )

# --- Модальное окно для ручного ввода времени ---
class TimeModal(Modal):
    def __init__(self, car_name: str):
        super().__init__(title=f"Взять машину: {car_name}")
        self.car_name = car_name
        
        self.time_input = TextInput(
            label="Время в минутах (1-120)",
            placeholder="Например: 30",
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
            
            # Запускаем таймер для автоматического освобождения
            asyncio.create_task(auto_free_timer(self.car_name, minutes))
            
            embed = discord.Embed(
                title="🚗 Машина взята",
                description=f"**{self.car_name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Кто взял", value=user_name, inline=True)
            embed.add_field(name="Время", value=f"{minutes} минут", inline=True)
            embed.add_field(name="До", value=end_time.strftime("%H:%M"), inline=True)
            embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
            
            await send_log(f"✅ **{user_name}** взял машину **{self.car_name}**", embed=embed)
            
            await interaction.response.send_message(
                f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
                ephemeral=False
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Введите число!",
                ephemeral=True
            )

# --- Автоматический таймер для освобождения машины ---
async def auto_free_timer(car_name: str, minutes: int):
    """Ждет указанное время и освобождает машину."""
    await asyncio.sleep(minutes * 60)  # Переводим минуты в секунды
    
    # Проверяем, не освободили ли машину раньше
    if car_name in cars and cars[car_name]["status"] == "Занята":
        await free_car_auto(car_name)

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

# --- Модальное окно для переименования машины ---
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

# --- Кнопки для взятия машин (7 штук) ---
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
            
            # Создаем View с кнопками времени
            view = TimeButtonsView(car_name)
            
            # Добавляем кнопку для ручного ввода
            manual_button = Button(label="✏️ Своё время", style=discord.ButtonStyle.secondary)
            
            async def manual_callback(interaction: discord.Interaction):
                await interaction.response.send_modal(TimeModal(car_name))
            
            manual_button.callback = manual_callback
            view.add_item(manual_button)
            
            await interaction.response.send_message(
                f"🚗 **{car_name}**\nВыберите время или введите своё:",
                view=view,
                ephemeral=True
            )
        return callback

# --- Кнопки освобождения (7 штук) ---
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
            
            embed = discord.Embed(
                title="🚗 Машина освобождена",
                description=f"**{car_name}**",
                color=discord.Color.orange()
            )
            embed.add_field(name="Кто освободил", value=user_name, inline=True)
            embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
            
            await send_log(f"✅ **{user_name}** освободил машину **{car_name}**", embed=embed)
            
            await interaction.response.send_message(
                f"✅ Машина '{car_name}' освобождена!",
                ephemeral=False
            )
        return callback

# --- Событие: бот готов ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    await tree.sync()
    await send_log(f"✅ Бот **{client.user}** запущен и готов к работе!")

# --- КОМАНДА: /cars ---
@tree.command(name="cars", description="Показать список машин с кнопками")
async def cars_command(interaction: discord.Interaction):
    car_list = generate_car_list()
    
    view = View(timeout=None)
    
    take_view = CarButtonsView()
    for item in take_view.children:
        view.add_item(item)
    
    free_view = FreeButtonsView()
    for item in free_view.children:
        view.add_item(item)
    
    await interaction.response.send_message(
        f"{car_list}\n\n**Кнопки:**\n🟢 Левая колонка - взять машину\n🔴 Правая колонка - освободить машину",
        view=view
    )

# --- КОМАНДА: /add_car ---
@tree.command(name="add_car", description="Добавить новую машину в список")
async def add_car_command(interaction: discord.Interaction):
    await interaction.response.send_modal(AddCarModal())

# --- КОМАНДА: /remove_car ---
@tree.command(name="remove_car", description="Удалить машину из списка")
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

# --- КОМАНДА: /rename_car ---
@tree.command(name="rename_car", description="Переименовать машину")
@app_commands.describe(car_name="Название машины для переименования")
async def rename_car_command(interaction: discord.Interaction, car_name: str):
    if car_name not in cars:
        await interaction.response.send_message(
            f"❌ Машина '{car_name}' не найдена!",
            ephemeral=True
        )
        return
    
    await interaction.response.send_modal(RenameCarModal(car_name))

# --- КОМАНДА: /list_cars ---
@tree.command(name="list_cars", description="Показать список машин без кнопок")
async def list_cars_command(interaction: discord.Interaction):
    car_list = generate_car_list()
    await interaction.response.send_message(car_list)

# --- КОМАНДА: /take ---
@tree.command(name="take", description="Взять машину на определенное время")
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

    # Запускаем таймер для автоматического освобождения
    asyncio.create_task(auto_free_timer(car_name, minutes))

    embed = discord.Embed(
        title="🚗 Машина взята",
        description=f"**{car_name}**",
        color=discord.Color.green()
    )
    embed.add_field(name="Кто взял", value=user_name, inline=True)
    embed.add_field(name="Время", value=f"{minutes} минут", inline=True)
    embed.add_field(name="До", value=end_time.strftime("%H:%M"), inline=True)
    embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    
    await send_log(f"✅ **{user_name}** взял машину **{car_name}**", embed=embed)

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

    embed = discord.Embed(
        title="🚗 Машина освобождена",
        description=f"**{car_name}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Кто освободил", value=user_name, inline=True)
    embed.set_footer(text=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    
    await send_log(f"✅ **{user_name}** освободил машину **{car_name}**", embed=embed)

    await interaction.response.send_message(
        f"✅ Машина '{car_name}' освобождена!"
    )

# --- ЗАПУСК БОТА ---
client.run(os.getenv('DISCORD_TOKEN'))