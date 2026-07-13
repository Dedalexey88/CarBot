import os
import discord
from discord import app_commands
from discord.ui import Button, View
import datetime

# --- Данные о машинах ---
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

# --- ID канала для логов (из переменной окружения) ---
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# --- Функция для отправки сообщения в лог-канал ---
async def send_log(message: str, embed: discord.Embed = None):
    """Отправляет сообщение в указанный канал."""
    if LOG_CHANNEL_ID == 0:
        print("⚠️ LOG_CHANNEL_ID не настроен!")
        return
    
    channel = client.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        print(f"❌ Канал с ID {LOG_CHANNEL_ID} не найден!")
        return
    
    if embed:
        await channel.send(message, embed=embed)
    else:
        await channel.send(message)

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
            
            # --- ОТПРАВКА В ЛОГ-КАНАЛ ---
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

# --- Класс для кнопок машин ---
class CarButtonsView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Karin Rebel", style=discord.ButtonStyle.success, custom_id="car_0")
    async def car_0(self, interaction: discord.Interaction, button: Button):
        if cars["Karin Rebel TS701VCA"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Karin Rebel TS701VCA"))
    
    @discord.ui.button(label="Benefactor Ml63", style=discord.ButtonStyle.success, custom_id="car_1")
    async def car_1(self, interaction: discord.Interaction, button: Button):
        if cars["Benefactor Ml63 2010 ST530MFA"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Benefactor Ml63 2010 ST530MFA"))
    
    @discord.ui.button(label="Annis Jook", style=discord.ButtonStyle.success, custom_id="car_2")
    async def car_2(self, interaction: discord.Interaction, button: Button):
        if cars["Annis Jook Nizmo RS 2013 JZ738CKY"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Annis Jook Nizmo RS 2013 JZ738CKY"))
    
    @discord.ui.button(label="Emperor IC-F", style=discord.ButtonStyle.success, custom_id="car_3")
    async def car_3(self, interaction: discord.Interaction, button: Button):
        if cars["Emperor IC-F 2012 BU363YHX"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Emperor IC-F 2012 BU363YHX"))
    
    @discord.ui.button(label="Benefactor G-series", style=discord.ButtonStyle.success, custom_id="car_4")
    async def car_4(self, interaction: discord.Interaction, button: Button):
        if cars["Benefactor G-series 63 ASG 6x6 LY699IEB"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Benefactor G-series 63 ASG 6x6 LY699IEB"))
    
    @discord.ui.button(label="Vapid Bronzo", style=discord.ButtonStyle.success, custom_id="car_5")
    async def car_5(self, interaction: discord.Interaction, button: Button):
        if cars["Vapid Bronzo Predator 2022 GC643UFN"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Vapid Bronzo Predator 2022 GC643UFN"))
    
    @discord.ui.button(label="Karin Thunder", style=discord.ButtonStyle.success, custom_id="car_6")
    async def car_6(self, interaction: discord.Interaction, button: Button):
        if cars["Karin Thunder 2021 SY108SFL"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Karin Thunder 2021 SY108SFL"))
    
    @discord.ui.button(label="Ocelot Lynx", style=discord.ButtonStyle.success, custom_id="car_7")
    async def car_7(self, interaction: discord.Interaction, button: Button):
        if cars["Ocelot Lynx 2019 HK742XAM"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Ocelot Lynx 2019 HK742XAM"))
    
    @discord.ui.button(label="Grotti Turismo", style=discord.ButtonStyle.success, custom_id="car_8")
    async def car_8(self, interaction: discord.Interaction, button: Button):
        if cars["Grotti Turismo R 2018 PM930SRL"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Grotti Turismo R 2018 PM930SRL"))
    
    @discord.ui.button(label="Pegassi Tempesta", style=discord.ButtonStyle.success, custom_id="car_9")
    async def car_9(self, interaction: discord.Interaction, button: Button):
        if cars["Pegassi Tempesta 2020 YF521KCD"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Pegassi Tempesta 2020 YF521KCD"))
    
    @discord.ui.button(label="Pfister Comet", style=discord.ButtonStyle.success, custom_id="car_10")
    async def car_10(self, interaction: discord.Interaction, button: Button):
        if cars["Pfister Comet SR 2022 XE876BFT"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Pfister Comet SR 2022 XE876BFT"))
    
    @discord.ui.button(label="Dewbauchee Vagner", style=discord.ButtonStyle.success, custom_id="car_11")
    async def car_11(self, interaction: discord.Interaction, button: Button):
        if cars["Dewbauchee Vagner 2023 TD210MXP"]["status"] == "Занята":
            await interaction.response.send_message("❌ Машина занята!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeModal("Dewbauchee Vagner 2023 TD210MXP"))

# --- Кнопки освобождения ---
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
        
        # --- ОТПРАВКА В ЛОГ-КАНАЛ ---
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

# --- Событие: бот готов ---
@client.event
async def on_ready():
    print(f'✅ Бот {client.user} готов к работе!')
    await tree.sync()
    
    # Отправляем приветствие в лог-канал
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

# --- ЗАПУСК БОТА ---
client.run(os.getenv('DISCORD_TOKEN'))