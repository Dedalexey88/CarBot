import os
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
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

# --- Модальное окно для ввода времени ---
class TimeModal(Modal):
    def __init__(self, car_name: str):
        super().__init__(title=f"Взять машину: {car_name}")
        self.car_name = car_name
        
        self.time_input = TextInput(
            label="Время в минутах (15-120)",
            placeholder="Например: 30",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.time_input.value)
            if minutes < 15 or minutes > 120:
                await interaction.response.send_message(
                    "❌ Время должно быть от 15 до 120 минут!",
                    ephemeral=True
                )
                return
            
            # Проверяем, свободна ли машина
            if cars[self.car_name]["status"] == "Занята":
                await interaction.response.send_message(
                    f"❌ Машина '{self.car_name}' уже занята!",
                    ephemeral=True
                )
                return
            
            # Бронируем машину
            user_name = interaction.user.display_name
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            cars[self.car_name]["status"] = "Занята"
            cars[self.car_name]["user"] = user_name
            cars[self.car_name]["end_time"] = end_time
            
            await interaction.response.send_message(
                f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
                ephemeral=False
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Введите число!",
                ephemeral=True
            )

# --- Кнопки для быстрого выбора времени ---
class TimeButtonsView(View):
    def __init__(self, car_name: str):
        super().__init__(timeout=60)
        self.car_name = car_name
    
    @discord.ui.button(label="15", style=discord.ButtonStyle.primary)
    async def time_15(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 15)
    
    @discord.ui.button(label="30", style=discord.ButtonStyle.primary)
    async def time_30(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 30)
    
    @discord.ui.button(label="45", style=discord.ButtonStyle.primary)
    async def time_45(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 45)
    
    @discord.ui.button(label="60", style=discord.ButtonStyle.primary)
    async def time_60(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 60)
    
    @discord.ui.button(label="90", style=discord.ButtonStyle.primary)
    async def time_90(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 90)
    
    @discord.ui.button(label="120", style=discord.ButtonStyle.primary)
    async def time_120(self, interaction: discord.Interaction, button: Button):
        await self.take_car(interaction, 120)
    
    async def take_car(self, interaction: discord.Interaction, minutes: int):
        # Проверяем, свободна ли машина
        if cars[self.car_name]["status"] == "Занята":
            await interaction.response.send_message(
                f"❌ Машина '{self.car_name}' уже занята!",
                ephemeral=True
            )
            return
        
        # Бронируем машину
        user_name = interaction.user.display_name
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        
        cars[self.car_name]["status"] = "Занята"
        cars[self.car_name]["user"] = user_name
        cars[self.car_name]["end_time"] = end_time
        
        await interaction.response.send_message(
            f"✅ Машина '{self.car_name}' взята пользователем **{user_name}** на **{minutes}** минут!",
            ephemeral=False
        )

# --- Класс для создания кнопок машин ---
class CarButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)  # Кнопки работают всегда
    
    @discord.ui.button(label="Karin Rebel", style=discord.ButtonStyle.success, custom_id="car_0")
    async def car_0(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Karin Rebel TS701VCA")
    
    @discord.ui.button(label="Benefactor Ml63", style=discord.ButtonStyle.success, custom_id="car_1")
    async def car_1(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Benefactor Ml63 2010 ST530MFA")
    
    @discord.ui.button(label="Annis Jook", style=discord.ButtonStyle.success, custom_id="car_2")
    async def car_2(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Annis Jook Nizmo RS 2013 JZ738CKY")
    
    @discord.ui.button(label="Emperor IC-F", style=discord.ButtonStyle.success, custom_id="car_3")
    async def car_3(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Emperor IC-F 2012 BU363YHX")
    
    @discord.ui.button(label="Benefactor G-series", style=discord.ButtonStyle.success, custom_id="car_4")
    async def car_4(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Benefactor G-series 63 ASG 6x6 LY699IEB")
    
    @discord.ui.button(label="Vapid Bronzo", style=discord.ButtonStyle.success, custom_id="car_5")
    async def car_5(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Vapid Bronzo Predator 2022 GC643UFN")
    
    @discord.ui.button(label="Karin Thunder", style=discord.ButtonStyle.success, custom_id="car_6")
    async def car_6(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Karin Thunder 2021 SY108SFL")
    
    @discord.ui.button(label="Ocelot Lynx", style=discord.ButtonStyle.success, custom_id="car_7")
    async def car_7(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Ocelot Lynx 2019 HK742XAM")
    
    @discord.ui.button(label="Grotti Turismo", style=discord.ButtonStyle.success, custom_id="car_8")
    async def car_8(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Grotti Turismo R 2018 PM930SRL")
    
    @discord.ui.button(label="Pegassi Tempesta", style=discord.ButtonStyle.success, custom_id="car_9")
    async def car_9(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Pegassi Tempesta 2020 YF521KCD")
    
    @discord.ui.button(label="Pfister Comet", style=discord.ButtonStyle.success, custom_id="car_10")
    async def car_10(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Pfister Comet SR 2022 XE876BFT")
    
    @discord.ui.button(label="Dewbauchee Vagner", style=discord.ButtonStyle.success, custom_id="car_11")
    async def car_11(self, interaction: discord.Interaction, button: Button):
        await self.handle_car(interaction, "Dewbauchee Vagner 2023 TD210MXP")
    
    async def handle_car(self, interaction: discord.Interaction, car_name: str):
        if cars[car_name]["status"] == "Занята":
            await interaction.response.send_message(
                f"❌ Машина '{car_name}' уже занята!",
                ephemeral=True
            )
            return
        
        # Показываем кнопки с выбором времени
        view = TimeButtonsView(car_name)
        await interaction.response.send_message(
            f"🚗 **{car_name}**\nВыберите время в минутах:",
            view=view,
            ephemeral=True
        )

# --- Кнопки освобождения машин ---
class FreeButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Освободить Karin Rebel", style=discord.ButtonStyle.danger, custom_id="free_0")
    async def free_0(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Karin Rebel TS701VCA")
    
    @discord.ui.button(label="Освободить Benefactor", style=discord.ButtonStyle.danger, custom_id="free_1")
    async def free_1(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Benefactor Ml63 2010 ST530MFA")
    
    @discord.ui.button(label="Освободить Annis", style=discord.ButtonStyle.danger, custom_id="free_2")
    async def free_2(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Annis Jook Nizmo RS 2013 JZ738CKY")
    
    @discord.ui.button(label="Освободить Emperor", style=discord.ButtonStyle.danger, custom_id="free_3")
    async def free_3(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Emperor IC-F 2012 BU363YHX")
    
    @discord.ui.button(label="Освободить G-series", style=discord.ButtonStyle.danger, custom_id="free_4")
    async def free_4(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Benefactor G-series 63 ASG 6x6 LY699IEB")
    
    @discord.ui.button(label="Освободить Bronzo", style=discord.ButtonStyle.danger, custom_id="free_5")
    async def free_5(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Vapid Bronzo Predator 2022 GC643UFN")
    
    @discord.ui.button(label="Освободить Thunder", style=discord.ButtonStyle.danger, custom_id="free_6")
    async def free_6(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Karin Thunder 2021 SY108SFL")
    
    @discord.ui.button(label="Освободить Lynx", style=discord.ButtonStyle.danger, custom_id="free_7")
    async def free_7(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Ocelot Lynx 2019 HK742XAM")
    
    @discord.ui.button(label="Освободить Turismo", style=discord.ButtonStyle.danger, custom_id="free_8")
    async def free_8(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Grotti Turismo R 2018 PM930SRL")
    
    @discord.ui.button(label="Освободить Tempesta", style=discord.ButtonStyle.danger, custom_id="free_9")
    async def free_9(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Pegassi Tempesta 2020 YF521KCD")
    
    @discord.ui.button(label="Освободить Comet", style=discord.ButtonStyle.danger, custom_id="free_10")
    async def free_10(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Pfister Comet SR 2022 XE876BFT")
    
    @discord.ui.button(label="Освободить Vagner", style=discord.ButtonStyle.danger, custom_id="free_11")
    async def free_11(self, interaction: discord.Interaction, button: Button):
        await self.free_car(interaction, "Dewbauchee Vagner 2023 TD210MXP")
    
    async def free_car(self, interaction: discord.Interaction, car_name: str):
        if cars[car_name]["status"] == "Свободна":
            await interaction.response.send_message(
                f"✅ Машина '{car_name}' уже свободна!",
                ephemeral=True
            )
            return
        
        # Проверяем, тот ли пользователь освобождает
        if cars[car_name]["user"] != interaction.user.display_name:
            await interaction.response.send_message(
                f"❌ Вы не можете освободить эту машину! Ее взял: {cars[car_name]['user']}",
                ephemeral=True
            )
            return
        
        cars[car_name]["status"] = "Свободна"
        cars[car_name]["user"] = None
        cars[car_name]["end_time"] = None
        
        await interaction.response.send_message(
            f"✅ Машина '{car_name}' освобождена!",
            ephemeral=False
        )

# --- Событие: бот готов ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    await tree.sync()

# --- КОМАНДА: /cars (с кнопками) ---
@tree.command(name="cars", description="Показать список машин с кнопками")
async def cars_command(interaction: discord.Interaction):
    """Отображает список машин с кнопками."""
    car_list = generate_car_list()
    
    # Создаем два ряда кнопок: взятие и освобождение
    view = View(timeout=None)
    
    # Добавляем кнопки для взятия машин
    take_view = CarButtonsView()
    for item in take_view.children:
        view.add_item(item)
    
    # Добавляем кнопки для освобождения машин
    free_view = FreeButtonsView()
    for item in free_view.children:
        view.add_item(item)
    
    await interaction.response.send_message(
        f"{car_list}\n\n**Кнопки:**\n🟢 Левая колонка - взять машину\n🔴 Правая колонка - освободить машину",
        view=view
    )

# --- ЗАПУСК БОТА ---
client.run(os.getenv('DISCORD_TOKEN'))