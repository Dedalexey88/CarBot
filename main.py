#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CarBot — Discord-бот учёта машин, контрактов, ВЗП и игровых оповещений.

Исправленная версия main.py. Ключевые отличия от исходника:
  * состояние машин сохраняется в JSON атомарно (дата аренды — ISO-строка);
  * таймеры аренды привязаны к «поколению» и не освобождают чужую аренду;
  * панель машин не превышает лимиты Discord (5 кнопок в ряд, до 25 компонентов);
  * сбор ВЗП имеет одно активное состояние, не перетирается старым таймером,
    корректно завершается при достижении цели и не превышает лимиты embed/UI;
  * фоновый цикл оповещений запускается один раз и не дублируется при реконнекте;
  * ошибки взаимодействий перехватываются и не «вешают» кнопки.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import io
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ui import Button, Modal, Select, TextInput, View

# ---------------------------------------------------------------------------
# Консоль и пути
# ---------------------------------------------------------------------------

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - зависит от терминала
        pass

BASE_DIR = Path(__file__).resolve().parent
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def load_dotenv(path: Path) -> None:
    """Минимальный аналог python-dotenv: KEY=VALUE из .env, не перетирая окружение."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        print(f"⚠️ Не удалось прочитать {path.name}: {exc}", file=sys.stderr)
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv(BASE_DIR / ".env")

DEFAULT_CARS = [
    "Karin Rebel TS701VCA",
    "Benefactor Ml63 2010 ST530MFA",
    "Annis Jook Nizmo RS 2013 JZ738CKY",
    "Emperor IC-F 2012 BU363YHX",
    "Benefactor G-series 63 ASG 6x6 LY699IEB",
    "Vapid Bronzo Predator 2022 GC643UFN",
    "Karin Thunder 2021 SY108SFL",
    "Ubermacht 760I J70 2022",
]

CAR_PAGE_SIZE = 5  # 5 кнопок «взять» + 5 «освободить» + навигация
CAR_MAX_MINUTES = 120
VZP_DURATION = 10 * 60
VZP_REMINDERS = (150, 300, 450)
VZP_MAX_MEMBERS = 25
CONTRACT_DURATION = 10 * 60
CONTRACT_NOTIFICATIONS = ((150, 7, 30), (300, 5, 0), (450, 2, 30))
CONTRACT_MIN_MEMBERS = 2
CONTRACT_MAX_MEMBERS = 3

CARS_FILE = Path(os.getenv("CARS_FILE") or (BASE_DIR / "cars_data.json"))


def env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"❌ Переменная {name} должна содержать число (Discord ID), получено: {raw!r}") from exc
    if value < 0:
        raise SystemExit(f"❌ Переменная {name} не может быть отрицательной")
    return value


GUILD_ID = env_int("GUILD_ID")
CONTRACT_CHANNEL_ID = env_int("CONTRACT_CHANNEL_ID")
CAR_CHANNEL_ID = env_int("CAR_CHANNEL_ID")
LOG_CHANNEL_ID = env_int("LOG_CHANNEL_ID")

# Каналы игровых событий. Можно переопределить через переменные окружения.
GW_CHANNEL_ID = env_int("GW_CHANNEL_ID", 1544246587918782504)
STREETWARS_CHANNEL_ID = env_int("STREETWARS_CHANNEL_ID", 1544246587918782504)
CHR_CHANNEL_ID = env_int("CHR_CHANNEL_ID", 1544246587918782504)
DROP_CHANNEL_ID = env_int("DROP_CHANNEL_ID", 1544246587918782504)
VZH_CHANNEL_ID = env_int("VZH_CHANNEL_ID", 1544246587918782504)

VZP_CHANNELS = [
    1523341052680081408,
    1538899458157318165,
    1523341229289640157,
]
VZP_CHANNEL_ID = VZP_CHANNELS[0]


def log(message: str) -> None:
    print(message, flush=True)


# ---------------------------------------------------------------------------
# Время
# ---------------------------------------------------------------------------


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_msk() -> dt.datetime:
    return now_utc().astimezone(MOSCOW_TZ)


def fmt_msk(value: Optional[dt.datetime]) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW_TZ)
    return value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")


def parse_datetime(value: Any) -> Optional[dt.datetime]:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        result = value
    else:
        try:
            result = dt.datetime.fromisoformat(str(value).strip())
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=MOSCOW_TZ)
    return result


def minute_key(moment: Optional[dt.datetime] = None) -> str:
    moment = moment or now_msk()
    return moment.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Хранилище машин
# ---------------------------------------------------------------------------

FREE = "Свободна"
BUSY = "Занята"


class CarStore:
    """Машины с сохранением на диск и безопасными таймерами аренды."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.cars: dict[str, dict[str, Any]] = {}
        self.on_expired: Optional[Callable[[str, dict[str, Any]], Any]] = None
        self._lock = asyncio.Lock()
        self._tokens: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # --- загрузка / сохранение -------------------------------------------------
    def load(self) -> None:
        data: dict[str, Any] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
                else:
                    log(f"⚠️ {self.path.name}: ожидался объект, получен {type(raw).__name__}. Использую значения по умолчанию.")
            except (OSError, json.JSONDecodeError) as exc:
                log(f"⚠️ Не удалось прочитать {self.path.name}: {exc}. Создаю новый файл.")
        if not data:
            data = {name: {"status": FREE, "user": None, "user_id": None, "end_time": None} for name in DEFAULT_CARS}

        cars: dict[str, dict[str, Any]] = {}
        for raw_name, record in data.items():
            name = str(raw_name).strip()
            if not name or not isinstance(record, dict):
                continue
            status = record.get("status")
            user_name = record.get("user") or None
            user_id = record.get("user_id")
            if not isinstance(user_id, int):
                user_id = None
            end_time = parse_datetime(record.get("end_time"))
            if status not in (FREE, BUSY):
                status = BUSY if (user_name or user_id) else FREE
            if status == BUSY and not (user_name or user_id):
                status = FREE
            if status == BUSY and end_time is None:
                # Аренда без срока не может истечь — освобождаем, чтобы не «висела».
                status, user_name, user_id = FREE, None, None
            cars[name] = {
                "status": status,
                "user": user_name,
                "user_id": user_id,
                "end_time": end_time,
            }
        self.cars = cars
        self.save()

    def _payload(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, data in self.cars.items():
            end_time = data.get("end_time")
            result[name] = {
                "status": data["status"],
                "user": data.get("user"),
                "user_id": data.get("user_id"),
                "end_time": end_time.isoformat() if isinstance(end_time, dt.datetime) else None,
            }
        return result

    def save(self) -> bool:
        """Атомарная запись: при сбое старый файл остаётся целым."""
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self._payload(), ensure_ascii=False, indent=4), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except (OSError, TypeError, ValueError) as exc:
            log(f"❌ Ошибка сохранения {self.path.name}: {exc}")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    # --- состояние -------------------------------------------------------------
    def get(self, name: str) -> Optional[dict[str, Any]]:
        return self.cars.get(name)

    def is_busy(self, name: str) -> bool:
        data = self.cars.get(name)
        return bool(data and data["status"] == BUSY)

    def status_line(self, name: str) -> str:
        data = self.cars.get(name) or {"status": FREE}
        if data["status"] != BUSY:
            return f"🟢 **{name}**: {FREE}"
        owner = data.get("user") or "неизвестно"
        end_time = data.get("end_time")
        if not end_time:
            return f"🔴 **{name}**: {BUSY} (взял: {owner})"
        remaining = (end_time - now_utc()).total_seconds()
        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            return f"🔴 **{name}**: {BUSY} (взял: {owner}, осталось {minutes} мин {seconds} сек, до {fmt_msk(end_time)})"
        return f"🔴 **{name}**: {BUSY} (взял: {owner}) ⏰ ВРЕМЯ ВЫШЛО"

    def list_text(self) -> str:
        lines = ["**🚗 Список машин:**"]
        lines.extend(self.status_line(name) for name in self.cars)
        return "\n".join(lines)

    # --- аренда ----------------------------------------------------------------
    async def take(self, name: str, user: discord.abc.User, minutes: int) -> tuple[bool, str]:
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return False, "Время должно быть числом минут."
        if not 1 <= minutes <= CAR_MAX_MINUTES:
            return False, f"Время должно быть от 1 до {CAR_MAX_MINUTES} минут."

        async with self._lock:
            data = self.cars.get(name)
            if data is None:
                return False, f"Машина «{name}» не найдена."
            if data["status"] == BUSY:
                owner = data.get("user") or "другой участник"
                return False, f"Машина «{name}» уже занята ({owner})."
            end_time = now_utc() + dt.timedelta(minutes=minutes)
            data.update(status=BUSY, user=user.display_name, user_id=user.id, end_time=end_time)
            self.save()
            self._schedule(name)

        return True, (
            f"Машина «{name}» взята на {minutes} мин. "
            f"Освободится автоматически в {fmt_msk(end_time)} (МСК)."
        )

    async def release(
        self,
        name: str,
        *,
        user: Optional[discord.abc.User] = None,
        force: bool = False,
    ) -> tuple[bool, Any]:
        async with self._lock:
            data = self.cars.get(name)
            if data is None:
                return False, f"Машина «{name}» не найдена."
            if data["status"] != BUSY:
                return False, f"Машина «{name}» уже свободна."
            if not force:
                if user is None:
                    return False, "Не указан пользователь."
                owner_id = data.get("user_id")
                if owner_id is not None and owner_id != user.id:
                    return False, f"Эту машину взял {data.get('user') or 'другой участник'}, освободить может только он."
                if owner_id is None and data.get("user") != user.display_name:
                    return False, f"Эту машину взял {data.get('user') or 'другой участник'}, освободить может только он."
            record = dict(data)
            data.update(status=FREE, user=None, user_id=None, end_time=None)
            self._cancel_timer(name)
            self.save()
        return True, record

    # --- таймеры ---------------------------------------------------------------
    def _cancel_timer(self, name: str) -> None:
        self._tokens.pop(name, None)
        task = self._tasks.pop(name, None)
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    def _schedule(self, name: str) -> None:
        data = self.cars.get(name)
        if not data or data["status"] != BUSY or not data.get("end_time"):
            return
        self._cancel_timer(name)
        token = uuid.uuid4().hex
        self._tokens[name] = token
        delay = max(0.0, (data["end_time"] - now_utc()).total_seconds())
        self._tasks[name] = asyncio.create_task(self._expire(name, token, delay))

    async def _expire(self, name: str, token: str, delay: float) -> None:
        try:
            while True:
                await asyncio.sleep(max(0.0, delay))
                if self._tokens.get(name) != token:
                    return
                data = self.cars.get(name)
                if not data or data["status"] != BUSY:
                    return
                end_time = data.get("end_time")
                if end_time is None:
                    return
                left = (end_time - now_utc()).total_seconds()
                if left > 0:  # системное время/сон могли сдвинуть таймер
                    delay = left
                    continue
                break
        except asyncio.CancelledError:
            raise

        async with self._lock:
            if self._tokens.get(name) != token:
                return
            data = self.cars.get(name)
            if not data or data["status"] != BUSY:
                return
            record = dict(data)
            data.update(status=FREE, user=None, user_id=None, end_time=None)
            self._tokens.pop(name, None)
            self._tasks.pop(name, None)
            self.save()

        if self.on_expired is not None:
            try:
                await self.on_expired(name, record)
            except Exception as exc:  # уведомление не должно ломать таймер
                log(f"❌ Ошибка обработчика истечения аренды {name}: {type(exc).__name__}: {exc}")

    async def restore_timers(self) -> None:
        """Восстанавливает таймеры после перезапуска бота."""
        for name, data in list(self.cars.items()):
            if data["status"] != BUSY:
                continue
            end_time = data.get("end_time")
            if end_time is None or end_time <= now_utc():
                ok, record = await self.release(name, force=True)
                if ok and self.on_expired is not None:
                    try:
                        await self.on_expired(name, record)
                    except Exception as exc:
                        log(f"❌ Ошибка обработчика аренды {name}: {exc}")
            else:
                self._schedule(name)

    def cancel_all_timers(self) -> None:
        for name in list(self._tasks):
            self._cancel_timer(name)


# ---------------------------------------------------------------------------
# Discord-клиент и общие помощники
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

cars_store = CarStore(CARS_FILE)
cars_store.load()

GW_TIMES = [
    (8, 30), (8, 35), (10, 30), (10, 35), (12, 30), (12, 35),
    (14, 30), (14, 35), (16, 30), (16, 35), (18, 30), (18, 35),
    (20, 30), (20, 35), (22, 30), (22, 35), (0, 30), (0, 35),
    (2, 30), (2, 35), (4, 30), (4, 35), (6, 30), (6, 35),
]
CHR_TIMES = [(19, 40), (19, 45), (19, 50), (19, 55), (20, 0)]
DROP_TIMES = [
    (1, 45), (2, 0), (4, 45), (5, 0), (7, 45), (8, 0), (10, 45), (11, 0),
    (13, 45), (14, 0), (16, 45), (17, 0), (19, 45), (20, 0), (22, 45), (23, 0),
]
VZH_TIMES = [(18, 10), (18, 50), (19, 0)]
VZH_DAYS = {
    0: "Общий", 1: "Мафии", 2: "Банды", 3: "Общий", 4: "Мафии", 5: "Банды", 6: "Общий",
}
STREETWARS_DAYS = {
    0: {"day": "Понедельник", "graffiti": "№11", "file": "11.png"},
    3: {"day": "Четверг", "graffiti": "№38", "file": "38.png"},
    5: {"day": "Суббота", "graffiti": "№46", "file": "46.png"},
}

gw_data = {"enabled": False, "last_key": None}
streetwars_data = {"enabled": False, "last_key": None}
chr_data = {"enabled": False, "last_key": None}
drop_data = {"enabled": False, "last_key": None}
vzh_data = {"enabled": False, "last_key": None}


async def respond(interaction: discord.Interaction, message: str, *, ephemeral: bool = True) -> None:
    """Ответ на взаимодействие с учётом уже отправленного ответа."""
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(message, ephemeral=ephemeral)


class SafeView(View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        log(f"❌ Ошибка кнопки: {type(error).__name__}: {error}")
        try:
            await respond(interaction, "❌ Не удалось выполнить действие. Попробуйте ещё раз.")
        except Exception:
            pass


class SafeModal(Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log(f"❌ Ошибка формы: {type(error).__name__}: {error}")
        try:
            await respond(interaction, "❌ Не удалось обработать форму. Попробуйте ещё раз.")
        except Exception:
            pass


def short_name(name: str, limit: int = 20) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def stable_id(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def clip_lines(lines: Iterable[str], limit: int = 1024) -> str:
    """Обрезает список строк так, чтобы значение поля embed помещалось в лимит."""
    lines = list(lines)
    if not lines:
        return "—"
    out: list[str] = []
    used = 0
    for line in lines:
        extra = len(line) + (1 if out else 0)
        if used + extra > limit - 40:
            break
        out.append(line)
        used += extra
    remaining = len(lines) - len(out)
    if remaining > 0:
        out.append(f"…и ещё {remaining}")
    return "\n".join(out) if out else (lines[0][: limit - 1] + "…")


# ---------------------------------------------------------------------------
# Логи и очистка каналов
# ---------------------------------------------------------------------------


async def send_log(message: str, embed: Optional[discord.Embed] = None) -> None:
    if not LOG_CHANNEL_ID:
        return
    channel = client.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        return
    try:
        if embed is not None:
            await channel.send(message, embed=embed)
        else:
            await channel.send(message)
    except discord.HTTPException as exc:
        log(f"⚠️ Не удалось отправить лог: {exc}")


async def cleanup_channel(channel_id: int, keep_last: int = 10, exclude_ids: Optional[list[int]] = None) -> None:
    """Удаляет старые сообщения только самого бота, сохраняя последние keep_last."""
    exclude = set(exclude_ids or [])
    channel = client.get_channel(channel_id)
    if channel is None:
        return
    try:
        messages = [msg async for msg in channel.history(limit=50)]
        candidates = [
            msg for msg in messages
            if msg.id not in exclude and not msg.pinned and client.user and msg.author.id == client.user.id
        ]
        if len(candidates) <= keep_last:
            return
        candidates.sort(key=lambda m: m.created_at)
        for msg in candidates[:-keep_last]:
            try:
                await msg.delete()
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass
    except discord.HTTPException as exc:
        log(f"⚠️ Ошибка очистки канала {channel_id}: {exc}")


# ---------------------------------------------------------------------------
# Кнопки времени и панель машин
# ---------------------------------------------------------------------------


class TimeInputModal(SafeModal):
    def __init__(self, store: CarStore, car_name: str):
        super().__init__(title=f"Взять машину: {short_name(car_name, 30)}")
        self.store = store
        self.car_name = car_name
        self.time_input = TextInput(
            label=f"Время в минутах (1-{CAR_MAX_MINUTES})",
            placeholder=f"Введите число от 1 до {CAR_MAX_MINUTES}",
            min_length=1,
            max_length=3,
            required=True,
        )
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            minutes = int(self.time_input.value.strip())
        except ValueError:
            await respond(interaction, "❌ Введите целое число минут.")
            return
        ok, message = await self.store.take(self.car_name, interaction.user, minutes)
        await respond(interaction, ("✅ " if ok else "❌ ") + message, ephemeral=not ok)
        if ok:
            await send_log(f"🚗 **{interaction.user.display_name}** взял **{self.car_name}** на {minutes} мин.")
            await update_car_panel()


class TimeButtonsView(SafeView):
    def __init__(self, store: CarStore, car_name: str):
        super().__init__(timeout=120)
        self.store = store
        self.car_name = car_name
        for index, minutes in enumerate((15, 30, 45, 60, 90, 120)):
            button = Button(
                label=f"{minutes} мин",
                style=discord.ButtonStyle.primary,
                row=index // 5,
                custom_id=f"cbt:{stable_id(car_name)}:{minutes}",
            )
            button.callback = partial(self._take, minutes=minutes)
            self.add_item(button)
        custom = Button(label="✏️ Своё время", style=discord.ButtonStyle.secondary, row=1,
                        custom_id=f"cbt:{stable_id(car_name)}:custom")
        custom.callback = self._custom
        self.add_item(custom)

    async def _custom(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(TimeInputModal(self.store, self.car_name))

    async def _take(self, interaction: discord.Interaction, *, minutes: int) -> None:
        ok, message = await self.store.take(self.car_name, interaction.user, minutes)
        await respond(interaction, ("✅ " if ok else "❌ ") + message, ephemeral=not ok)
        if ok:
            await send_log(f"🚗 **{interaction.user.display_name}** взял **{self.car_name}** на {minutes} мин.")
            await update_car_panel()


class CarPanelView(SafeView):
    """Панель машин: 5 машин на страницу, ряды по 5 кнопок (лимит Discord соблюдён)."""

    def __init__(self, store: CarStore, page: int = 0):
        super().__init__(timeout=None)
        self.store = store
        names = list(store.cars)
        pages = max(1, math.ceil(len(names) / CAR_PAGE_SIZE))
        page = max(0, min(page, pages - 1))
        self.page = page
        self.pages = pages
        chunk = names[page * CAR_PAGE_SIZE: (page + 1) * CAR_PAGE_SIZE]

        for name in chunk:
            button = Button(
                label=f"🟢 {short_name(name)}",
                style=discord.ButtonStyle.success,
                row=0,
                custom_id=f"cp:t:{stable_id(name)}:{page}",
            )
            button.callback = partial(self._take, name=name)
            self.add_item(button)

        for name in chunk:
            button = Button(
                label=f"🔴 {short_name(name)}",
                style=discord.ButtonStyle.danger,
                row=1,
                custom_id=f"cp:f:{stable_id(name)}:{page}",
            )
            button.callback = partial(self._free, name=name)
            self.add_item(button)

        if pages > 1:
            prev = Button(label="◀", style=discord.ButtonStyle.secondary, row=2,
                          disabled=page == 0, custom_id=f"cp:p:{page}")
            prev.callback = partial(self._nav, page=page - 1)
            self.add_item(prev)

            counter = Button(label=f"{page + 1}/{pages}", style=discord.ButtonStyle.secondary,
                             row=2, disabled=True, custom_id=f"cp:n:{page}")
            self.add_item(counter)

            nxt = Button(label="▶", style=discord.ButtonStyle.secondary, row=2,
                         disabled=page >= pages - 1, custom_id=f"cp:x:{page}")
            nxt.callback = partial(self._nav, page=page + 1)
            self.add_item(nxt)

    def _text(self) -> str:
        text = (
            f"{self.store.list_text()}\n\n"
            f"**Кнопки:**\n"
            f"🟢 первая строка — взять машину\n"
            f"🔴 вторая строка — освободить машину"
        )
        if self.pages > 1:
            text += f"\n\n📄 Страница {self.page + 1}/{self.pages}"
        return text

    async def _take(self, interaction: discord.Interaction, *, name: str) -> None:
        data = self.store.get(name)
        if data is None:
            await respond(interaction, f"❌ Машина «{name}» больше не существует.")
            return
        if data["status"] == BUSY:
            await respond(interaction, f"❌ Машина «{name}» уже занята ({data.get('user') or 'другой участник'}).")
            return
        await interaction.response.send_message(
            f"🚗 **{name}**\nВыберите время (1-{CAR_MAX_MINUTES} мин):",
            view=TimeButtonsView(self.store, name),
            ephemeral=True,
        )

    async def _free(self, interaction: discord.Interaction, *, name: str) -> None:
        ok, message = await self.store.release(name, user=interaction.user)
        if not ok:
            await respond(interaction, f"❌ {message}")
            return
        await respond(interaction, f"✅ Машина «{name}» освобождена!", ephemeral=False)
        await send_log(f"✅ **{interaction.user.display_name}** освободил **{name}**")
        await update_car_panel()

    async def _nav(self, interaction: discord.Interaction, *, page: int) -> None:
        view = CarPanelView(self.store, page)
        await interaction.response.edit_message(content=view._text(), view=view)


panel_lock = asyncio.Lock()


async def update_car_panel() -> None:
    if not CAR_CHANNEL_ID:
        return
    async with panel_lock:
        channel = client.get_channel(CAR_CHANNEL_ID)
        if channel is None:
            log(f"❌ Канал машин не найден! ID: {CAR_CHANNEL_ID}")
            return
        view = CarPanelView(cars_store, 0)
        try:
            message = await channel.send(view._text(), view=view)
        except discord.HTTPException as exc:
            log(f"❌ Не удалось отправить панель машин: {exc}")
            return
        await cleanup_channel(CAR_CHANNEL_ID, keep_last=2, exclude_ids=[message.id])


async def handle_car_expired(name: str, record: dict[str, Any]) -> None:
    embed = discord.Embed(
        title="⏰ Машина автоматически освобождена",
        description=f"**{name}**",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Кто брал", value=str(record.get("user") or "—"), inline=True)
    embed.set_footer(text=fmt_msk(now_utc()))
    await send_log(f"⏰ Время аренды **{name}** истекло — машина освобождена.", embed=embed)
    await update_car_panel()


cars_store.on_expired = handle_car_expired


# ---------------------------------------------------------------------------
# Контракты
# ---------------------------------------------------------------------------

contracts: dict[str, dict[str, Any]] = {}
contracts_lock = asyncio.Lock()


def contract_remaining_text(contract: dict[str, Any]) -> str:
    remaining = CONTRACT_DURATION - (now_utc() - contract["created_at"]).total_seconds()
    remaining = max(0, int(remaining))
    return f"{remaining // 60} мин {remaining % 60} сек"


def build_contract_embed(contract: dict[str, Any], *, status: str = "⏳ Набор участников") -> discord.Embed:
    members = contract["members"]
    member_lines = [
        f"• {item['name']} — {item.get('skill', 'Не указаны')}" for item in members.values()
    ]
    embed = discord.Embed(title="📋 Контракт", description=f"**{contract['name']}**", color=discord.Color.blue())
    embed.add_field(name="Создал", value=contract["author"], inline=True)
    embed.add_field(name="Статус", value=f"{status} ({len(members)}/{CONTRACT_MAX_MEMBERS})", inline=True)
    embed.add_field(name="Осталось времени", value=contract_remaining_text(contract), inline=True)
    embed.add_field(name="Минимум", value=f"{CONTRACT_MIN_MEMBERS} человека", inline=True)
    embed.add_field(
        name=f"👥 Участники ({len(members)} человек)",
        value=clip_lines(member_lines) if member_lines else "🔴 Нет участников",
        inline=False,
    )
    embed.set_footer(text="Нажмите кнопку ниже, чтобы записаться или отказаться")
    return embed


def build_contract_view(contract_id: str) -> View:
    view = View(timeout=None)
    view.add_item(ContractJoinButton(contract_id))
    view.add_item(CancelContractButton(contract_id))
    return view


async def create_contract(author: discord.abc.User, name: str) -> Optional[str]:
    name = name.strip()
    if not name:
        return None
    if len(name) > 100:
        name = name[:100]
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал контрактов не найден! ID: {CONTRACT_CHANNEL_ID}")
        return None

    contract_id = f"{author.id}-{uuid.uuid4().hex[:8]}"
    async with contracts_lock:
        contracts[contract_id] = {
            "id": contract_id,
            "name": name,
            "author": getattr(author, "display_name", str(author)),
            "author_id": author.id,
            "members": {},
            "created_at": now_utc(),
            "message_id": None,
            "notifications": [],
            "timer_task": None,
            "finished": False,
        }
        contract = contracts[contract_id]

    try:
        message = await channel.send(
            content="@Контракт @everyone",
            embed=build_contract_embed(contract),
            view=build_contract_view(contract_id),
        )
    except discord.HTTPException as exc:
        log(f"❌ Не удалось отправить контракт: {exc}")
        contracts.pop(contract_id, None)
        return None

    contract["message_id"] = message.id
    contract["timer_task"] = asyncio.create_task(contract_timer(contract_id))
    return contract_id


async def update_contract_message(contract_id: str) -> None:
    contract = contracts.get(contract_id)
    if contract is None:
        return
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        return
    embed = build_contract_embed(contract)
    view = build_contract_view(contract_id)
    message_id = contract.get("message_id")
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(content="@Контракт @everyone", embed=embed, view=view)
            return
        except discord.HTTPException:
            contract["message_id"] = None
    try:
        message = await channel.send(content="@Контракт @everyone", embed=embed, view=view)
    except discord.HTTPException as exc:
        log(f"❌ Не удалось обновить контракт: {exc}")
        return
    contract["message_id"] = message.id


class SkillSelectView(SafeView):
    def __init__(self, contract_id: str):
        super().__init__(timeout=60)
        self.contract_id = contract_id
        self.select = Select(
            placeholder="Выберите уровень навыков",
            options=[
                discord.SelectOption(label="🔹 Слабые", value="weak", description="Базовый уровень"),
                discord.SelectOption(label="🔸 Средние", value="medium", description="Средний уровень"),
                discord.SelectOption(label="🔺 Сильные", value="strong", description="Высокий уровень"),
            ],
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._select
        self.add_item(self.select)

    async def _select(self, interaction: discord.Interaction) -> None:
        contract = contracts.get(self.contract_id)
        if contract is None or contract.get("finished"):
            await respond(interaction, "❌ Контракт уже завершён!")
            return
        user_id = str(interaction.user.id)
        if user_id in contract["members"]:
            await respond(interaction, "❌ Вы уже записаны!")
            return
        if len(contract["members"]) >= CONTRACT_MAX_MEMBERS:
            await respond(interaction, "❌ Контракт уже укомплектован (3 человека)!")
            return
        skills = {"weak": "🔹 Слабые", "medium": "🔸 Средние", "strong": "🔺 Сильные"}
        skill = skills.get(self.select.values[0], "Не указаны")
        contract["members"][user_id] = {"name": interaction.user.display_name, "skill": skill}
        await respond(interaction, f"✅ Вы записались на контракт с навыками: **{skill}**!")
        await update_contract_message(self.contract_id)
        if len(contract["members"]) >= CONTRACT_MAX_MEMBERS:
            await finish_contract(self.contract_id)


class ContractJoinButton(Button):
    def __init__(self, contract_id: str):
        super().__init__(label="✅ Вступить на выполнение контракта", style=discord.ButtonStyle.success,
                         custom_id=f"contract_join_{contract_id}")
        self.contract_id = contract_id

    async def callback(self, interaction: discord.Interaction) -> None:
        contract = contracts.get(self.contract_id)
        if contract is None or contract.get("finished"):
            await respond(interaction, "❌ Контракт уже завершён или не существует!")
            return
        if str(interaction.user.id) in contract["members"]:
            await respond(interaction, "❌ Вы уже записаны на этот контракт!")
            return
        if len(contract["members"]) >= CONTRACT_MAX_MEMBERS:
            await respond(interaction, "❌ Контракт уже укомплектован!")
            return
        await interaction.response.send_message(
            "📝 **Выберите уровень ваших навыков:**",
            view=SkillSelectView(self.contract_id),
            ephemeral=True,
        )


class CancelContractButton(Button):
    def __init__(self, contract_id: str):
        super().__init__(label="❌ Отказаться от выполнения", style=discord.ButtonStyle.danger,
                         custom_id=f"cancel_contract_{contract_id}")
        self.contract_id = contract_id

    async def callback(self, interaction: discord.Interaction) -> None:
        contract = contracts.get(self.contract_id)
        if contract is None or contract.get("finished"):
            await respond(interaction, "❌ Контракт уже завершён!")
            return
        user_id = str(interaction.user.id)
        if user_id not in contract["members"]:
            await respond(interaction, "❌ Вы не записаны на этот контракт!")
            return
        del contract["members"][user_id]
        await respond(interaction, "❌ Вы отказались от выполнения контракта!")
        await update_contract_message(self.contract_id)


async def send_contract_notification(contract_id: str, minutes: int, seconds: int = 0) -> None:
    contract = contracts.get(contract_id)
    if contract is None or contract.get("finished"):
        return
    if len(contract["members"]) >= CONTRACT_MAX_MEMBERS:
        return
    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    if channel is None:
        return
    needed = CONTRACT_MAX_MEMBERS - len(contract["members"])
    time_text = f"{minutes} мин {seconds} сек" if seconds else f"{minutes} минут"
    try:
        message = await channel.send(
            f"@Контракт @everyone\n⏰ **Осталось {time_text}!**\n"
            f"Скорее записывайтесь в контракт **{contract['name']}**!\n"
            f"Нужно ещё **{needed}** человек."
        )
    except discord.HTTPException as exc:
        log(f"⚠️ Не удалось отправить напоминание по контракту: {exc}")
        return
    contract["notifications"].append(message.id)


async def contract_timer(contract_id: str) -> None:
    try:
        for at, minutes, seconds in CONTRACT_NOTIFICATIONS:
            delay = at - (now_utc() - contracts[contract_id]["created_at"]).total_seconds()
            await asyncio.sleep(max(0.0, delay))
            await send_contract_notification(contract_id, minutes, seconds)
        delay = CONTRACT_DURATION - (now_utc() - contracts[contract_id]["created_at"]).total_seconds()
        await asyncio.sleep(max(0.0, delay))
        await finish_contract(contract_id, timed_out=True)
    except asyncio.CancelledError:
        raise
    except KeyError:
        return
    except Exception as exc:
        log(f"❌ Ошибка таймера контракта {contract_id}: {type(exc).__name__}: {exc}")


async def finish_contract(contract_id: str, *, timed_out: bool = False) -> None:
    contract = contracts.get(contract_id)
    if contract is None or contract.get("finished"):
        return
    contract["finished"] = True

    task = contract.get("timer_task")
    if task is not None and task is not asyncio.current_task():
        task.cancel()

    channel = client.get_channel(CONTRACT_CHANNEL_ID)
    members = contract["members"]

    if channel is not None:
        for message_id in contract.get("notifications", []):
            try:
                msg = await channel.fetch_message(message_id)
                await msg.delete()
            except discord.HTTPException:
                pass
        message_id = contract.get("message_id")
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.delete()
            except discord.HTTPException:
                pass

    success = len(members) >= CONTRACT_MIN_MEMBERS

    if channel is not None:
        try:
            if success:
                embed = discord.Embed(title="✅ Контракт сформирован!", description=f"**{contract['name']}**",
                                      color=discord.Color.green())
                embed.add_field(name="Создал", value=contract["author"], inline=True)
                lines = [f"**{item['name']}**\n  📊 Навыки: {item.get('skill', 'Не указаны')}" for item in members.values()]
                embed.add_field(name=f"👥 Участники ({len(members)} человек)",
                                value=clip_lines(lines), inline=False)
                embed.set_footer(text="Удачи в выполнении контракта! 🍀")
                message = await channel.send(content="@Контракт @everyone", embed=embed)
                await cleanup_channel(CONTRACT_CHANNEL_ID, keep_last=10, exclude_ids=[message.id])
            else:
                lines = [f"• {item['name']}" for item in members.values()] or ["🔴 Никто не записался"]
                await channel.send(
                    f"❌ **Сбор на контракт «{contract['name']}» провалился!**\n"
                    f"**Создал:** {contract['author']}\n"
                    f"**Записалось:** {len(members)} человек\n"
                    f"**Список записавшихся:**\n{clip_lines(lines)}"
                )
        except discord.HTTPException as exc:
            log(f"⚠️ Не удалось опубликовать итог контракта: {exc}")

    contracts.pop(contract_id, None)


async def contract_message_handler(message: discord.Message) -> None:
    content = message.content.strip()
    prefix = None
    lowered = content.lower()
    if lowered.startswith("/contr"):
        prefix = content[:6]
    elif lowered.startswith("!контракт"):
        prefix = content[:9]
    if prefix is None:
        return
    name = content[len(prefix):].strip()
    if not name:
        return
    await create_contract(message.author, name)
    try:
        await message.delete()
    except discord.HTTPException:
        pass


# ---------------------------------------------------------------------------
# ВЗП
# ---------------------------------------------------------------------------


@dataclass
class VzpSession:
    generation: str
    channel_id: int
    author_id: int
    text: str
    kind: str
    target: int
    started_at: dt.datetime
    members: dict[int, dict[str, Any]] = field(default_factory=dict)
    selections: dict[int, int] = field(default_factory=dict)
    message_id: Optional[int] = None
    task: Optional[asyncio.Task] = None
    finished: bool = False

    @property
    def kind_label(self) -> str:
        return "⚔️ Атака" if self.kind == "attack" else "🛡️ Защита"

    @property
    def kind_emoji(self) -> str:
        return "⚔️" if self.kind == "attack" else "🛡️"

    def pending(self) -> dict[int, dict[str, Any]]:
        return {uid: data for uid, data in self.members.items() if data.get("approved") is None}

    def seconds_left(self) -> int:
        return max(0, int(VZP_DURATION - (now_utc() - self.started_at).total_seconds()))


vzp_session: Optional[VzpSession] = None
vzp_lock = asyncio.Lock()


def build_vzp_embed(session: VzpSession) -> discord.Embed:
    pending = [f"• {data['name']}" for data in session.members.values() if data.get("approved") is None]
    approved = [f"• {data['name']}" for data in session.members.values() if data.get("approved") is True]
    rejected = [f"• {data['name']}" for data in session.members.values() if data.get("approved") is False]

    left = session.seconds_left()
    if left > 0:
        time_left = f"⏰ Осталось: {left // 60} мин {left % 60} сек"
    else:
        time_left = "⏰ Время вышло!"

    embed = discord.Embed(
        title=f"{session.kind_emoji} Сбор на ВЗП",
        description=f"**{session.text}**",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="📊 Статус",
        value=f"Тип: {session.kind_label}\nУчастников: {len(session.members)}/{session.target}\n{time_left}",
        inline=False,
    )
    if pending:
        embed.add_field(name="⏳ Ожидают подтверждения", value=clip_lines(pending), inline=False)
    if approved:
        embed.add_field(name="✅ Подтверждены", value=clip_lines(approved), inline=False)
    if rejected:
        embed.add_field(name="❌ Отклонены", value=clip_lines(rejected), inline=False)
    embed.set_footer(text="Нажмите кнопку, чтобы записаться или отписаться")
    return embed


class VzpView(SafeView):
    def __init__(self, session: VzpSession):
        super().__init__(timeout=None)
        self.session = session
        generation = session.generation[:8]

        join = Button(label="✅ Записаться на ВЗП", style=discord.ButtonStyle.success,
                      custom_id=f"vzp_join_{generation}", row=0)
        join.callback = self._join
        self.add_item(join)

        leave = Button(label="❌ Отписаться от ВЗП", style=discord.ButtonStyle.danger,
                       custom_id=f"vzp_leave_{generation}", row=0)
        leave.callback = self._leave
        self.add_item(leave)

        pending = list(session.pending().items())[:VZP_MAX_MEMBERS]
        if pending:
            options = [
                discord.SelectOption(label=short_name(data["name"], 100), value=str(uid))
                for uid, data in pending
            ]
            self.select = Select(placeholder="Участник для подтверждения", options=options,
                                 min_values=1, max_values=1, row=1,
                                 custom_id=f"vzp_pick_{generation}")
            self.select.callback = self._select_member
            self.add_item(self.select)

            approve = Button(label="✅ Подтвердить", style=discord.ButtonStyle.success,
                             custom_id=f"vzp_ok_{generation}", row=2)
            approve.callback = self._approve_selected
            self.add_item(approve)

            reject = Button(label="❌ Отклонить", style=discord.ButtonStyle.danger,
                            custom_id=f"vzp_no_{generation}", row=2)
            reject.callback = self._reject_selected
            self.add_item(reject)

    def _current(self) -> Optional[VzpSession]:
        session = self.session
        if session.finished or vzp_session is not session:
            return None
        return session

    async def _join(self, interaction: discord.Interaction) -> None:
        session = self._current()
        if session is None:
            await respond(interaction, "❌ Сбор уже завершён!")
            return
        user_id = interaction.user.id
        if user_id in session.members:
            await respond(interaction, "❌ Вы уже записаны!")
            return
        if len(session.members) >= session.target:
            await respond(interaction, f"❌ Достигнут максимум участников ({session.target})!")
            return
        session.members[user_id] = {"name": interaction.user.display_name, "approved": None}
        await respond(interaction, "✅ Вы записались на ВЗП!")
        if len(session.members) >= session.target:
            await finish_vzp(session, success=True)
        else:
            await update_vzp_message(session)

    async def _leave(self, interaction: discord.Interaction) -> None:
        session = self._current()
        if session is None:
            await respond(interaction, "❌ Сбор уже завершён!")
            return
        user_id = interaction.user.id
        if user_id not in session.members:
            await respond(interaction, "❌ Вы не записаны!")
            return
        del session.members[user_id]
        await respond(interaction, "❌ Вы отписались от ВЗП!")
        await update_vzp_message(session)

    async def _select_member(self, interaction: discord.Interaction) -> None:
        session = self._current()
        if session is None:
            await respond(interaction, "❌ Сбор уже завершён!")
            return
        if interaction.user.id != session.author_id:
            await respond(interaction, "❌ Только создатель сбора может подтверждать участников!")
            return
        try:
            user_id = int(self.select.values[0])
        except (IndexError, TypeError, ValueError):
            await respond(interaction, "❌ Не удалось определить участника.")
            return
        if user_id not in session.members:
            await respond(interaction, "❌ Участник не найден!")
            return
        session.selections[interaction.user.id] = user_id
        await respond(
            interaction,
            f"Выбран **{session.members[user_id]['name']}**. Нажмите ✅ Подтвердить или ❌ Отклонить.",
        )

    async def _reject_selected(self, interaction: discord.Interaction) -> None:
        await self._set_approval(interaction, False)

    async def _approve_selected(self, interaction: discord.Interaction) -> None:
        await self._set_approval(interaction, True)

    async def _set_approval(self, interaction: discord.Interaction, approved: bool) -> None:
        session = self._current()
        if session is None:
            await respond(interaction, "❌ Сбор уже завершён!")
            return
        if interaction.user.id != session.author_id:
            await respond(interaction, "❌ Только создатель сбора может подтверждать участников!")
            return
        user_id = session.selections.get(interaction.user.id)
        if user_id is None or user_id not in session.members:
            await respond(interaction, "❌ Выберите участника в списке!")
            return
        session.members[user_id]["approved"] = approved
        name = session.members[user_id]["name"]
        await respond(interaction, f"{'✅' if approved else '❌'} {name} {'подтверждён' if approved else 'отклонён'}!")
        await update_vzp_message(session)


async def update_vzp_message(session: VzpSession) -> None:
    if session.finished:
        return
    channel = client.get_channel(session.channel_id)
    if channel is None:
        log(f"❌ Канал ВЗП не найден! ID: {session.channel_id}")
        return
    embed = build_vzp_embed(session)
    view = VzpView(session) if not session.finished else None

    if session.message_id:
        try:
            message = await channel.fetch_message(session.message_id)
            await message.edit(content="@everyone", embed=embed, view=view)
            return
        except discord.HTTPException:
            session.message_id = None

    try:
        message = await channel.send(content="@everyone", embed=embed, view=view)
    except discord.HTTPException as exc:
        log(f"❌ Не удалось отправить сообщение ВЗП: {exc}")
        return
    session.message_id = message.id


async def create_vzp(interaction: discord.Interaction, *, kind: str, text: str, target: int) -> None:
    global vzp_session
    if interaction.channel_id not in VZP_CHANNELS:
        await respond(interaction, "❌ Команда доступна только в каналах ВЗП!")
        return
    if not 1 <= target <= VZP_MAX_MEMBERS:
        await respond(interaction, f"❌ Количество участников должно быть от 1 до {VZP_MAX_MEMBERS}!")
        return
    async with vzp_lock:
        if vzp_session is not None and not vzp_session.finished:
            await respond(interaction, "❌ Сбор на ВЗП уже идёт! Дождитесь его завершения.")
            return
        session = VzpSession(
            generation=uuid.uuid4().hex,
            channel_id=interaction.channel_id,
            author_id=interaction.user.id,
            text=text.strip() or "Сбор реакций на ВЗП!",
            kind="attack" if kind == "attack" else "defense",
            target=target,
            started_at=now_utc(),
        )
        vzp_session = session

    await update_vzp_message(session)
    session.task = asyncio.create_task(vzp_timer(session))
    await respond(
        interaction,
        f"✅ Сбор на ВЗП создан!\n**Тип:** {session.kind_label}\n"
        f"**Текст:** {session.text}\n**Максимум участников:** {target}",
    )


async def vzp_timer(session: VzpSession) -> None:
    try:
        for at in VZP_REMINDERS:
            delay = at - (now_utc() - session.started_at).total_seconds()
            await asyncio.sleep(max(0.0, delay))
            if session.finished or vzp_session is not session:
                return
            channel = client.get_channel(session.channel_id)
            if channel is not None:
                left = session.seconds_left()
                try:
                    await channel.send(
                        f"@everyone\n⏰ **Скорее записывайтесь на ВЗП!**\n"
                        f"Осталось: {left // 60} мин {left % 60} сек\n"
                        f"Участников: {len(session.members)}/{session.target}"
                    )
                except discord.HTTPException as exc:
                    log(f"⚠️ Напоминание ВЗП не отправлено: {exc}")
        delay = VZP_DURATION - (now_utc() - session.started_at).total_seconds()
        await asyncio.sleep(max(0.0, delay))
        if session.finished or vzp_session is not session:
            return
        await finish_vzp(session, success=False)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log(f"❌ Ошибка таймера ВЗП: {type(exc).__name__}: {exc}")


async def finish_vzp(session: VzpSession, *, success: bool) -> None:
    global vzp_session
    if session.finished:
        return
    session.finished = True

    task = session.task
    if task is not None and task is not asyncio.current_task():
        task.cancel()

    channel = client.get_channel(session.channel_id)
    if channel is not None:
        if session.message_id:
            try:
                message = await channel.fetch_message(session.message_id)
                await message.delete()
            except discord.HTTPException:
                pass

        approved = [data["name"] for data in session.members.values() if data.get("approved") is True]
        everyone = [data["name"] for data in session.members.values()]
        if success:
            embed = discord.Embed(
                title=f"{session.kind_emoji} Сбор на ВЗП успешно завершён!",
                description=f"**{session.text}**",
                color=discord.Color.green(),
            )
            if approved:
                going = clip_lines([f"• {name}" for name in approved])
            elif everyone:
                going = clip_lines([f"• {name} (без подтверждения)" for name in everyone])
            else:
                going = "🔴 Нет участников"
            embed.add_field(name="👥 Идут в теру", value=going, inline=False)
            embed.set_footer(text="Вперёд парни, принесите Дону победу!")
        else:
            embed = discord.Embed(
                title=f"{session.kind_emoji} Сбор на ВЗП провалился!",
                description=f"**{session.text}**\nНе набрано участников за 10 минут.",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="📋 Список записавшихся",
                value=clip_lines([f"• {name}" for name in everyone]) if everyone else "🔴 Никто не записался",
                inline=False,
            )
            embed.set_footer(text="Попробуйте снова!")
        try:
            await channel.send(content="@everyone", embed=embed)
        except discord.HTTPException as exc:
            log(f"⚠️ Не удалось опубликовать итог ВЗП: {exc}")

    if vzp_session is session:
        vzp_session = None


def get_vzp_maps() -> list[dict[str, str]]:
    folder = BASE_DIR / "vzp_maps"
    if not folder.is_dir():
        return []
    maps: list[dict[str, str]] = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            maps.append({"name": path.stem, "path": str(path)})
    return maps


class VzpMapButton(Button):
    def __init__(self, map_name: str, file_path: str, *, row: int = 0):
        super().__init__(label=short_name(map_name, 80), style=discord.ButtonStyle.primary,
                         custom_id=f"vzp_map_{stable_id(file_path)}", row=row)
        self.map_name = map_name
        self.file_path = Path(file_path)

    async def callback(self, interaction: discord.Interaction) -> None:
        suffix = self.file_path.suffix.lower() or ".png"
        filename = f"vzp_map_{stable_id(self.file_path)}{suffix}"
        try:
            data = self.file_path.read_bytes()
        except OSError as exc:
            log(f"❌ Не удалось прочитать карту {self.map_name}: {exc}")
            await respond(interaction, f"❌ Не удалось загрузить карту {self.map_name}")
            return
        file = discord.File(fp=io.BytesIO(data), filename=filename)
        embed = discord.Embed(title=f"🗺️ Карта: {self.map_name}", color=discord.Color.blue())
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="VZP Карта")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


class VzpMapsView(SafeView):
    def __init__(self, maps: list[dict[str, str]]):
        super().__init__(timeout=None)
        for index, item in enumerate(maps[:25]):
            self.add_item(VzpMapButton(item["name"], item["path"], row=index // 5))


# ---------------------------------------------------------------------------
# Оповещения
# ---------------------------------------------------------------------------


def check_notification(data: dict[str, Any], times: list[tuple[int, int]], moment: Optional[dt.datetime] = None) -> bool:
    if not data.get("enabled"):
        return False
    moment = moment or now_msk()
    key = minute_key(moment)
    if data.get("last_key") == key:
        return False
    return (moment.hour, moment.minute) in times


async def _send_with_optional_file(channel: discord.abc.Messageable, content: str, path: Path,
                                   filename: str) -> None:
    if path.is_file():
        try:
            await channel.send(content, file=discord.File(str(path), filename=filename))
            return
        except (discord.HTTPException, OSError) as exc:
            log(f"⚠️ Не удалось отправить файл {path.name}: {exc}")
    else:
        log(f"⚠️ Файл {path} не найден — отправляю текст")
    await channel.send(content)


async def send_gw_notification() -> None:
    if not gw_data["enabled"]:
        return
    channel = client.get_channel(GW_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал GW не найден! ID: {GW_CHANNEL_ID}")
        return
    now = now_msk()
    if now.minute not in (30, 35):
        return
    interval = f"{now.hour:02d}:30 — {now.hour:02d}:59"
    await channel.send(
        "@everyone\n"
        "🎨 **Граффити Вар!**\n"
        f"⏰ Время: **{interval}** (по МСК)\n"
        "🏃 **ВЗЯЛИ БАЛОНЫ В РУКИ И ВЫЕХАЛИ КРАСИТЬ ГЕТТО!**"
    )
    gw_data["last_key"] = minute_key(now)
    log(f"✅ Оповещение GW отправлено в {now:%H:%M}")


def should_send_streetwars(moment: Optional[dt.datetime] = None) -> bool:
    if not streetwars_data.get("enabled"):
        return False
    moment = moment or now_msk()
    if (moment.hour, moment.minute) != (21, 0):
        return False
    if moment.weekday() not in STREETWARS_DAYS:
        return False
    return streetwars_data.get("last_key") != minute_key(moment)


async def send_streetwars_notification() -> None:
    if not streetwars_data.get("enabled"):
        return
    channel = client.get_channel(STREETWARS_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал Street Wars не найден! ID: {STREETWARS_CHANNEL_ID}")
        return
    now = now_msk()
    day_info = STREETWARS_DAYS.get(now.weekday())
    if day_info is None:
        return
    message = (
        "@everyone\n"
        "🏁 **Street Wars!**\n"
        f"📅 День: **{day_info['day']}**\n"
        "⏰ Время: **21:00 - 21:30** (по МСК)\n"
        f"🎨 Графитка: **{day_info['graffiti']}**\n"
        "🏃 **Все заряжаемся / групп на мероприятие Street Wars!**"
    )
    await _send_with_optional_file(channel, message, BASE_DIR / "graffiti" / day_info["file"], day_info["file"])
    streetwars_data["last_key"] = minute_key(now)
    log(f"✅ Оповещение Street Wars отправлено в {now:%H:%M}")


async def send_chr_notification() -> None:
    if not chr_data.get("enabled"):
        return
    channel = client.get_channel(CHR_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал Чёрного рынка не найден! ID: {CHR_CHANNEL_ID}")
        return
    now = now_msk()
    message = (
        "@everyone\n"
        "🖤 **Чёрный рынок!**\n"
        "⏰ Время: **19:40 - 20:00** (по МСК)\n"
        "🏃 **Все заряжаемся / групп на мероприятие \"Чёрный рынок\"!**"
    )
    await _send_with_optional_file(channel, message, BASE_DIR / "foto" / "blackmarket.png", "blackmarket.png")
    chr_data["last_key"] = minute_key(now)
    log(f"✅ Оповещение Чёрного рынка отправлено в {now:%H:%M}")


async def send_drop_notification() -> None:
    if not drop_data.get("enabled"):
        return
    channel = client.get_channel(DROP_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал ДРОП не найден! ID: {DROP_CHANNEL_ID}")
        return
    now = now_msk()
    message = (
        "@everyone\n"
        "📦 **ДРОП - Воздушный Груз!**\n"
        f"⏰ Время: **{now:%H:%M}** (по МСК)\n"
        "🏃 **Все заряжаемся / групп на ДРОП!**"
    )
    await _send_with_optional_file(channel, message, BASE_DIR / "foto" / "airdrop.jpg", "airdrop.jpg")
    drop_data["last_key"] = minute_key(now)
    log(f"✅ Оповещение ДРОП отправлено в {now:%H:%M}")


async def send_vzh_notification() -> None:
    if not vzh_data.get("enabled"):
        return
    channel = client.get_channel(VZH_CHANNEL_ID)
    if channel is None:
        log(f"❌ Канал ВЗХ не найден! ID: {VZH_CHANNEL_ID}")
        return
    now = now_msk()
    if (now.hour, now.minute) == (18, 10):
        action, time_text = "🏗️ **Первое объявление — делаем строй!**", "18:10"
    elif (now.hour, now.minute) == (18, 50):
        action, time_text = "📢 **Объявление на Прок терры!**", "18:50"
    elif (now.hour, now.minute) == (19, 0):
        action, time_text = "🚨 **НАЧАЛО СОБЫТИЯ!**", "19:00"
    else:
        return
    day_type = VZH_DAYS.get(now.weekday(), "Общий")
    message = (
        "@everyone\n"
        "🔨 **ВЗХ - Война за Хаммеры!**\n"
        f"📅 День: **{day_type}**\n"
        f"⏰ Время: **{time_text}** (по МСК)\n"
        f"{action}\n"
        "🏃 **Все на ВЗХ - Войну за Хаммеры!**"
    )
    await _send_with_optional_file(channel, message, BASE_DIR / "foto" / "hammer.png", "hammer.png")
    vzh_data["last_key"] = minute_key(now)
    log(f"✅ Оповещение ВЗХ отправлено в {now:%H:%M} ({day_type})")


async def notification_loop() -> None:
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if check_notification(gw_data, GW_TIMES):
                await send_gw_notification()
            if check_notification(chr_data, CHR_TIMES):
                await send_chr_notification()
            if check_notification(drop_data, DROP_TIMES):
                await send_drop_notification()
            if check_notification(vzh_data, VZH_TIMES):
                await send_vzh_notification()
            if should_send_streetwars():
                await send_streetwars_notification()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log(f"❌ Ошибка в цикле оповещений: {type(exc).__name__}: {exc}")
        await asyncio.sleep(10)


# ---------------------------------------------------------------------------
# События клиента
# ---------------------------------------------------------------------------

checker_started = False


def guild_object() -> Optional[discord.Object]:
    return discord.Object(id=GUILD_ID) if GUILD_ID else None


async def sync_commands() -> None:
    guild = guild_object()
    try:
        if guild is not None:
            synced = await tree.sync(guild=guild)
        else:
            synced = await tree.sync()
        log(f"✅ Команды синхронизированы: {[cmd.name for cmd in synced]}")
    except Exception as exc:
        log(f"❌ Ошибка синхронизации команд: {type(exc).__name__}: {exc}")


def print_startup_diagnostics() -> None:
    log(f"📁 Текущая директория: {os.getcwd()}")
    log(f"📁 Файл машин: {CARS_FILE}")
    log(f"📁 Загружено машин: {len(cars_store.cars)}")
    if not GUILD_ID:
        log("⚠️ GUILD_ID не задан — команды будут глобальными (синхронизация может занять до часа).")
    for channel_id in VZP_CHANNELS:
        channel = client.get_channel(channel_id)
        log(f"{'✅' if channel else '❌'} Канал ВЗП: {getattr(channel, 'name', channel_id)}")
    for channel_id, name in [
        (GW_CHANNEL_ID, "GW"), (STREETWARS_CHANNEL_ID, "Street Wars"), (CHR_CHANNEL_ID, "Чёрный рынок"),
        (DROP_CHANNEL_ID, "ДРОП"), (VZH_CHANNEL_ID, "ВЗХ"), (CONTRACT_CHANNEL_ID, "Контракты"),
        (CAR_CHANNEL_ID, "Машины"), (LOG_CHANNEL_ID, "Логи"),
    ]:
        if not channel_id:
            continue
        channel = client.get_channel(channel_id)
        log(f"{'✅' if channel else '❌'} Канал {name}: {getattr(channel, 'name', channel_id)}")
    for folder in ("graffiti", "foto", "vzp_maps"):
        log(f"{'✅' if (BASE_DIR / folder).is_dir() else '❌'} Папка {folder}")


@client.event
async def on_ready() -> None:
    global checker_started
    log(f"✅ Бот {client.user} готов к работе!")

    if checker_started:
        log("🔄 Переподключение — фоновые задачи уже запущены.")
        return
    checker_started = True

    print_startup_diagnostics()
    await cars_store.restore_timers()

    if CAR_CHANNEL_ID:
        await update_car_panel()

    await sync_commands()
    asyncio.create_task(notification_loop())
    await send_log(f"✅ Бот **{client.user}** запущен!")


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author == client.user or message.author.bot:
        return
    if not CONTRACT_CHANNEL_ID or message.channel.id != CONTRACT_CHANNEL_ID:
        return
    await contract_message_handler(message)


@client.event
async def on_disconnect() -> None:
    log("⚠️ Соединение с Discord потеряно, переподключаюсь…")


# ---------------------------------------------------------------------------
# Слэш-команды
# ---------------------------------------------------------------------------


def command(*, name: str, description: str):
    return tree.command(name=name, description=description, guild=guild_object())


@command(name="contr", description="Создать новый контракт")
@app_commands.describe(name="Название контракта")
async def contr_command(interaction: discord.Interaction, name: str) -> None:
    if interaction.channel_id != CONTRACT_CHANNEL_ID:
        await respond(interaction, f"❌ Эта команда доступна только в канале <#{CONTRACT_CHANNEL_ID}>!")
        return
    contract_id = await create_contract(interaction.user, name)
    if contract_id is None:
        await respond(interaction, "❌ Не удалось создать контракт (проверьте канал и права бота).")
        return
    await respond(interaction, f"✅ Контракт **{name.strip()[:100]}** успешно создан!")


@contr_command.autocomplete("name")
async def contr_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=short_name(item["name"], 100), value=item["name"])
        for item in list(contracts.values())[:25]
        if current.lower() in item["name"].lower()
    ]


class VzpTextModal(SafeModal):
    def __init__(self, kind: str, channel_id: int):
        super().__init__(title="Создать сбор на ВЗП")
        self.kind = kind
        self.channel_id = channel_id
        self.vzp_text = TextInput(
            label="Текст сбора",
            placeholder="Введите текст для сбора",
            default="Сбор реакций на ВЗП!",
            required=True,
            max_length=200,
        )
        self.add_item(self.vzp_text)
        self.vzp_count = TextInput(
            label=f"Максимум участников (1-{VZP_MAX_MEMBERS})",
            placeholder="Например: 10",
            default="10",
            required=True,
            max_length=2,
        )
        self.add_item(self.vzp_count)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.channel_id != self.channel_id:
            await respond(interaction, "❌ Форма открыта в другом канале, создайте сбор заново.")
            return
        try:
            count = int(self.vzp_count.value.strip())
        except ValueError:
            await respond(interaction, "❌ Введите целое число участников.")
            return
        await create_vzp(interaction, kind=self.kind, text=self.vzp_text.value, target=count)


class VzpTypeView(SafeView):
    def __init__(self, channel_id: int):
        super().__init__(timeout=120)
        self.channel_id = channel_id
        attack = Button(label="⚔️ Атака", style=discord.ButtonStyle.danger, custom_id=f"vzp_type_attack_{channel_id}")
        attack.callback = self._attack
        self.add_item(attack)
        defense = Button(label="🛡️ Защита", style=discord.ButtonStyle.primary, custom_id=f"vzp_type_defense_{channel_id}")
        defense.callback = self._defense
        self.add_item(defense)

    async def _attack(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(VzpTextModal("attack", self.channel_id))

    async def _defense(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(VzpTextModal("defense", self.channel_id))


@command(name="vzpgo", description="Создать сбор на ВЗП")
async def vzpgo_command(interaction: discord.Interaction) -> None:
    if interaction.channel_id not in VZP_CHANNELS:
        mentions = " ".join(f"<#{channel_id}>" for channel_id in VZP_CHANNELS)
        await respond(interaction, f"❌ Эта команда доступна только в каналах: {mentions}!")
        return
    if vzp_session is not None and not vzp_session.finished:
        await respond(interaction, "❌ Сбор уже идёт! Дождитесь его завершения.")
        return
    embed = discord.Embed(
        title="⚔️ Создание сбора на ВЗП",
        description="**Выберите тип сбора:**\n⚔️ **Атака** — наступательные действия\n🛡️ **Защита** — оборонительные действия",
        color=discord.Color.blue(),
    )
    embed.set_footer(text="Выберите тип, затем введите текст и количество участников")
    await interaction.response.send_message(embed=embed, view=VzpTypeView(interaction.channel_id), ephemeral=True)


@command(name="vzp_maps", description="Показать все карты VZP")
async def vzp_maps_command(interaction: discord.Interaction) -> None:
    maps = get_vzp_maps()
    if not maps:
        await respond(interaction, "❌ **Карты не найдены!**\nУбедитесь, что папка `vzp_maps` существует.")
        return
    embed = discord.Embed(
        title="🗺️ Карты VZP",
        description=f"**Найдено карт: {len(maps)}**\n\nНажмите на кнопку с названием карты, чтобы увидеть её.",
        color=discord.Color.blue(),
    )
    embed.add_field(name="📋 Список карт:", value=clip_lines([f"• {item['name']}" for item in maps]), inline=False)
    embed.set_footer(text="Нажмите на кнопку ниже, чтобы посмотреть карту")
    await interaction.response.send_message(embed=embed, view=VzpMapsView(maps))


def notify_toggle_command(name: str, description: str, data: dict[str, Any], *, enable: bool,
                          on_text: str, off_text: str, already_on: str, already_off: str):
    async def handler(interaction: discord.Interaction) -> None:
        if data.get("enabled") is enable:
            await respond(interaction, already_on if enable else already_off)
            return
        data["enabled"] = enable
        data["last_key"] = None
        await respond(interaction, on_text if enable else off_text)

    return command(name=name, description=description)(handler)


gw_on_command = notify_toggle_command(
    "gw_on", "Включить оповещения о Граффити Вар", gw_data, enable=True,
    on_text=f"🔔 **Оповещения о Граффити Вар включены!**\n📢 Канал: <#{GW_CHANNEL_ID}>\n⏰ Оповещения в :30 и :35 каждого часа",
    off_text="", already_on="🔔 **Оповещения о Граффити Вар уже включены!**", already_off="",
)
gw_off_command = notify_toggle_command(
    "gw_off", "Отключить оповещения о Граффити Вар", gw_data, enable=False,
    on_text="", off_text="🔕 **Оповещения о Граффити Вар отключены!**",
    already_on="", already_off="🔕 **Оповещения о Граффити Вар уже отключены!**",
)
streetwar_on_command = notify_toggle_command(
    "streetwar_on", "Включить оповещения о Street Wars", streetwars_data, enable=True,
    on_text="🔔 **Оповещения о Street Wars включены!**\n📅 Дни: Понедельник, Четверг, Суббота\n⏰ Время: 21:00 (по МСК)",
    off_text="", already_on="🔔 **Оповещения о Street Wars уже включены!**", already_off="",
)
streetwar_off_command = notify_toggle_command(
    "streetwar_off", "Отключить оповещения о Street Wars", streetwars_data, enable=False,
    on_text="", off_text="🔕 **Оповещения о Street Wars отключены!**",
    already_on="", already_off="🔕 **Оповещения о Street Wars уже отключены!**",
)
chr_on_command = notify_toggle_command(
    "chr_on", "Включить оповещения о Чёрном рынке", chr_data, enable=True,
    on_text="🔔 **Оповещения о Чёрном рынке включены!**\n⏰ Время: 19:40, 19:45, 19:50, 19:55, 20:00 (МСК)",
    off_text="", already_on="🔔 **Оповещения о Чёрном рынке уже включены!**", already_off="",
)
chr_off_command = notify_toggle_command(
    "chr_off", "Отключить оповещения о Чёрном рынке", chr_data, enable=False,
    on_text="", off_text="🔕 **Оповещения о Чёрном рынке отключены!**",
    already_on="", already_off="🔕 **Оповещения о Чёрном рынке уже отключены!**",
)
drop_on_command = notify_toggle_command(
    "drop_on", "Включить оповещения о ДРОП - Воздушный Груз", drop_data, enable=True,
    on_text=(
        "🔔 **Оповещения о ДРОП включены!**\n"
        f"📢 Канал: <#{DROP_CHANNEL_ID}>\n⏰ 01:45, 02:00, 04:45, 05:00, 07:45, 08:00, 10:45, 11:00,\n"
        "13:45, 14:00, 16:45, 17:00, 19:45, 20:00, 22:45, 23:00 (МСК)"
    ),
    off_text="", already_on="🔔 **Оповещения о ДРОП уже включены!**", already_off="",
)
drop_off_command = notify_toggle_command(
    "drop_off", "Отключить оповещения о ДРОП - Воздушный Груз", drop_data, enable=False,
    on_text="", off_text="🔕 **Оповещения о ДРОП отключены!**",
    already_on="", already_off="🔕 **Оповещения о ДРОП уже отключены!**",
)
vzh_on_command = notify_toggle_command(
    "vzh_on", "Включить оповещения о ВЗХ - Война за Хаммеры", vzh_data, enable=True,
    on_text=(
        "🔔 **Оповещения о ВЗХ включены!**\n"
        f"📢 Канал: <#{VZH_CHANNEL_ID}>\n⏰ 18:10 — строй, 18:50 — Прок терры, 19:00 — начало события (МСК)"
    ),
    off_text="", already_on="🔔 **Оповещения о ВЗХ уже включены!**", already_off="",
)
vzh_off_command = notify_toggle_command(
    "vzh_off", "Отключить оповещения о ВЗХ - Война за Хаммеры", vzh_data, enable=False,
    on_text="", off_text="🔕 **Оповещения о ВЗХ отключены!**",
    already_on="", already_off="🔕 **Оповещения о ВЗХ уже отключены!**",
)


@command(name="streetwar_test", description="Показать информацию о Street Wars")
async def streetwar_test_command(interaction: discord.Interaction) -> None:
    embed = discord.Embed(title="🏁 Street Wars - Информация", description="Оповещения приходят в **21:00**",
                          color=discord.Color.blue())
    for data in STREETWARS_DAYS.values():
        exists = (BASE_DIR / "graffiti" / data["file"]).is_file()
        embed.add_field(
            name=f"📅 {data['day']}",
            value=f"🖼️ Графитка: **{data['graffiti']}**\n📁 Файл: {'✅ Найден' if exists else '❌ Не найден'}",
            inline=True,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@command(name="cars", description="Обновить список машин")
async def cars_command(interaction: discord.Interaction) -> None:
    if interaction.channel_id != CAR_CHANNEL_ID:
        await respond(interaction, f"❌ Команда доступна только в канале <#{CAR_CHANNEL_ID}>!")
        return
    await respond(interaction, "🔄 Обновляю список машин...")
    await update_car_panel()


@command(name="add_car", description="Добавить новую машину")
@app_commands.describe(car_name="Название новой машины")
async def add_car_command(interaction: discord.Interaction, car_name: str) -> None:
    car_name = car_name.strip()
    if not car_name:
        await respond(interaction, "❌ Название машины не может быть пустым!")
        return
    if car_name in cars_store.cars:
        await respond(interaction, f"❌ Машина «{car_name}» уже существует!")
        return
    if len(cars_store.cars) >= 100:
        await respond(interaction, "❌ Достигнут лимит в 100 машин.")
        return
    cars_store.cars[car_name] = {"status": FREE, "user": None, "user_id": None, "end_time": None}
    cars_store.save()
    await send_log(f"➕ **{interaction.user.display_name}** добавил машину: **{car_name}**")
    await respond(interaction, f"✅ Машина «{car_name}» успешно добавлена!", ephemeral=False)
    await update_car_panel()


@command(name="remove_car", description="Удалить машину")
@app_commands.describe(car_name="Название машины для удаления")
async def remove_car_command(interaction: discord.Interaction, car_name: str) -> None:
    if car_name not in cars_store.cars:
        await respond(interaction, f"❌ Машина «{car_name}» не найдена!")
        return
    if cars_store.is_busy(car_name):
        await respond(interaction, f"❌ Нельзя удалить машину «{car_name}» — она занята!")
        return
    del cars_store.cars[car_name]
    cars_store.save()
    await send_log(f"❌ **{interaction.user.display_name}** удалил машину: **{car_name}**")
    await respond(interaction, f"✅ Машина «{car_name}» успешно удалена!", ephemeral=False)
    await update_car_panel()


@command(name="rename_car", description="Переименовать машину")
@app_commands.describe(old_name="Текущее название машины", new_name="Новое название машины")
async def rename_car_command(interaction: discord.Interaction, old_name: str, new_name: str) -> None:
    old_name, new_name = old_name.strip(), new_name.strip()
    if not old_name or not new_name:
        await respond(interaction, "❌ Название не может быть пустым!")
        return
    if old_name not in cars_store.cars:
        await respond(interaction, f"❌ Машина «{old_name}» не найдена!")
        return
    if cars_store.is_busy(old_name):
        await respond(interaction, f"❌ Нельзя переименовать машину «{old_name}» — она занята!")
        return
    if new_name in cars_store.cars:
        await respond(interaction, f"❌ Машина «{new_name}» уже существует!")
        return
    cars_store.cars[new_name] = cars_store.cars.pop(old_name)
    cars_store.save()
    await send_log(f"✏️ **{interaction.user.display_name}** переименовал машину: **{old_name}** → **{new_name}**")
    await respond(interaction, f"✅ Машина «{old_name}» переименована в «{new_name}»!", ephemeral=False)
    await update_car_panel()


@command(name="list_cars", description="Показать список машин без кнопок")
async def list_cars_command(interaction: discord.Interaction) -> None:
    await respond(interaction, cars_store.list_text())


async def car_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    current = current.lower()
    return [
        app_commands.Choice(name=short_name(name, 100), value=name)
        for name in list(cars_store.cars)[:25]
        if current in name.lower()
    ]


@command(name="take", description="Взять машину")
@app_commands.describe(car_name="Название машины", minutes="Время в минутах (от 1 до 120)")
async def take_command(interaction: discord.Interaction, car_name: str,
                       minutes: app_commands.Range[int, 1, CAR_MAX_MINUTES]) -> None:
    ok, message = await cars_store.take(car_name, interaction.user, minutes)
    await respond(interaction, ("✅ " if ok else "❌ ") + message, ephemeral=not ok)
    if ok:
        await send_log(f"🚗 **{interaction.user.display_name}** взял **{car_name}** на {minutes} мин.")
        await update_car_panel()


@take_command.autocomplete("car_name")
async def take_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return await car_autocomplete(interaction, current)


@command(name="free", description="Освободить машину")
@app_commands.describe(car_name="Название машины")
async def free_command(interaction: discord.Interaction, car_name: str) -> None:
    ok, result = await cars_store.release(car_name, user=interaction.user)
    if not ok:
        await respond(interaction, f"❌ {result}")
        return
    await respond(interaction, f"✅ Машина «{car_name}» освобождена!", ephemeral=False)
    await send_log(f"✅ **{interaction.user.display_name}** освободил **{car_name}**")
    await update_car_panel()


@free_command.autocomplete("car_name")
async def free_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return await car_autocomplete(interaction, current)


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------


def run_bot() -> int:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        log("❌ ОШИБКА: DISCORD_TOKEN не найден в переменных окружения!")
        log("   Windows PowerShell:  $env:DISCORD_TOKEN='ваш_токен'; python main.py")
        log("   Linux/macOS:         DISCORD_TOKEN='ваш_токен' python main.py")
        return 1
    if not GUILD_ID:
        log("⚠️ GUILD_ID не задан: команды будут глобальными и появятся не сразу.")
    try:
        client.run(token)
    except discord.LoginFailure:
        log("❌ Неверный DISCORD_TOKEN — Discord отклонил вход.")
        return 1
    except discord.PrivilegedIntentsRequired:
        log("❌ Включите SERVER MEMBERS INTENT и MESSAGE CONTENT INTENT в Developer Portal.")
        return 1
    except KeyboardInterrupt:
        log("👋 Бот остановлен.")
    finally:
        try:
            cars_store.cancel_all_timers()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(run_bot())
