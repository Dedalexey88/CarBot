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
    
    # Определяем формат count x count
    count = vzp_data["attack_target"]
    
    embed = discord.Embed(
        title=f"⚔️ Война за предприятия! {count} x {count}",
        description="**Удачи парни, принесите Дону победу!**",
        color=discord.Color.gold()
    )
    
    attack_text = "\n".join([f"• {name}" for name in attack_list]) if attack_list else "🔴 Нет участников"
    defense_text = "\n".join([f"• {name}" for name in defense_list]) if defense_list else "🔴 Нет участников"
    
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
        # Удаляем только старые сообщения с кнопками
        messages_to_delete = []
        
        if vzp_data["attack_message_id"]:
            try:
                msg = await channel.fetch_message(vzp_data["attack_message_id"])
                messages_to_delete.append(msg)
                vzp_data["attack_message_id"] = None
            except:
                pass
        
        if vzp_data["defense_message_id"]:
            try:
                msg = await channel.fetch_message(vzp_data["defense_message_id"])
                messages_to_delete.append(msg)
                vzp_data["defense_message_id"] = None
            except:
                pass
        
        for msg in messages_to_delete:
            try:
                await msg.delete()
                await asyncio.sleep(0.3)
            except:
                pass
        
        # Отправляем финальное сообщение (НЕ УДАЛЯЕМ)
        final_msg = await channel.send(content="@everyone", embed=embed)
        vzp_data["final_message_id"] = final_msg.id
        
        print(f"✅ Финальное сообщение VZP отправлено (ID: {final_msg.id})")