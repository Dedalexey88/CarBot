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