from aiogram import Router, types, F
from aiogram.enums import ContentType
from database import handle_violation
from media_processor import process_text, process_photo, process_video, process_sticker
from filters import TextModelFilter, HasInlineMarkup, HasUrlFilter, NotModerator, IsModerator
from config import TOXICITY_THRESHOLD_TEXT, MOD_CHAT_ID
from datetime import datetime, timedelta
from database import db_conn
from aiogram.filters import Command
import asyncio

router = Router()

@router.message(lambda message: message.new_chat_members or message.left_chat_member)
async def delete_service_messages(message: types.Message):
    await message.delete()

@router.message(HasUrlFilter(), NotModerator())
async def telegraph_message_handler(message: types.Message):
    bot = message.bot
    if message.entities:
        for entity in message.entities:
            if entity.type == 'url' and message.text:
                url = message.text[entity.offset:entity.offset + entity.length]
            elif entity.type == 'text_link' and hasattr(entity, 'url'):
                url = entity.url
            else:
                continue
            if url and url.startswith('http'):
                await bot.forward_message(chat_id=MOD_CHAT_ID, from_chat_id=message.chat.id,message_id=message.message_id)
                await bot.send_message(MOD_CHAT_ID, f"Сообщение от {message.from_user.id} содержит ссылку")
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                break
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == 'url' and message.text:
                url = message.text[entity.offset:entity.offset + entity.length]
            elif entity.type == 'text_link' and hasattr(entity, 'url'):
                url = entity.url
            else:
                continue
            if url and url.startswith('http') :
                await bot.forward_message(chat_id=MOD_CHAT_ID, from_chat_id=message.chat.id, message_id=message.message_id)
                await bot.send_message(MOD_CHAT_ID,f"Сообщение от {message.from_user.id} содержит ссылку")
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                break
@router.message(HasInlineMarkup(),NotModerator())
async def handle_inline_markup_message(message: types.Message):
    await message.bot.forward_message(chat_id=MOD_CHAT_ID, from_chat_id=message.chat.id, message_id=message.message_id)
    await message.bot.send_message(MOD_CHAT_ID, f"Сообщение от {message.from_user.id} содержит inline-кнопки")
    await message.delete()

@router.message(F.content_type == ContentType.TEXT, TextModelFilter(),NotModerator())
async def handle_text(message: types.Message, text_model):
    result = await process_text(text_model, message.text)
    if result['toxicity'] > TOXICITY_THRESHOLD_TEXT:
        await handle_violation(message, 'toxic_text', message.text)
        await message.bot.delete_message(message.chat.id, message.message_id)


@router.message(F.content_type == ContentType.PHOTO, TextModelFilter(),NotModerator())
async def handle_photo(message: types.Message, text_model):
    bot = message.bot
    file = await message.bot.get_file(message.photo[-1].file_id)
    result_photo = await process_photo(bot, text_model, file)
    violation_found = False
    if result_photo['is_violation']:
        await handle_violation(message, result_photo['violation_type'], result_photo['content'])
        violation_found = True
    if message.caption:
        result_caption = await process_text(text_model, message.caption)
        if result_caption['toxicity'] > TOXICITY_THRESHOLD_TEXT:
            await handle_violation(message, 'toxic_caption', message.caption)
            violation_found = True
        if 'http' in message.caption or 't.me' in message.caption:
            await message.bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
            await message.bot.send_message(MOD_CHAT_ID, f"Подозрительная ссылка в подписи от {message.from_user.id}")
            violation_found = True
    if violation_found:
        await message.bot.delete_message(message.chat.id, message.message_id)


@router.message(F.content_type == ContentType.VIDEO, TextModelFilter(),NotModerator())
async def handle_video(message: types.Message, text_model):
    bot = message.bot
    if message.caption:
        result_caption = await process_text(text_model, message.caption)
        if result_caption['toxicity'] > TOXICITY_THRESHOLD_TEXT:
            await handle_violation(message, 'toxic_caption', message.caption)
            await bot.delete_message(message.chat.id, message.message_id)
            return
        if 'http' in message.caption.lower() or 't.me' in message.caption.lower():
            await bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
            await bot.send_message(MOD_CHAT_ID, f"Подозрительная ссылка в подписи от {message.from_user.id}")
            await bot.delete_message(message.chat.id, message.message_id)
            return
    if message.video.thumb:
        thumb_file = await bot.get_file(message.video.thumb.get("file_id"))
        result_thumb = await process_photo(bot, text_model, thumb_file)
        if result_thumb['is_violation']:
            await handle_violation(message, result_thumb['violation_type'], result_thumb['content'])
            await bot.delete_message(message.chat.id, message.message_id)
            return
    try:
        file = await bot.get_file(message.video.file_id)
        result_video = await process_video(bot, text_model, file)
        if result_video['is_violation']:
            await handle_violation(message, result_video['violation_type'], result_video['content'])
            await bot.delete_message(message.chat.id, message.message_id)
    except:
        await bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
        await bot.send_message(MOD_CHAT_ID, f"Большое видео от {message.from_user.id}, требует ручной проверки")
        await bot.delete_message(message.chat.id, message.message_id)


@router.message(F.content_type == ContentType.STICKER, TextModelFilter(),NotModerator())
async def handle_sticker(message: types.Message, text_model):
    bot = message.bot
    result = await process_sticker(bot, text_model, message.sticker)
    if result['is_violation']:
        await handle_violation(message, result['violation_type'], result['content'])
        await message.bot.delete_message(message.chat.id, message.message_id)

@router.message(F.content_type == ContentType.DOCUMENT,NotModerator())
async def handle_document(message: types.Message):
    await message.bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
    await message.bot.send_message(MOD_CHAT_ID, f"Подозрительный файл от {message.from_user.id}")
    await message.bot.delete_message(message.chat.id, message.message_id)

@router.message(F.content_type == ContentType.ANIMATION, TextModelFilter(),NotModerator())
async def handle_animation(message: types.Message, text_model):
    bot = message.bot
    file = await bot.get_file(message.animation.file_id)
    result = await process_video(bot, text_model, file)
    if result.get('is_violation'):
        await handle_violation(message, result['violation_type'], result['content'])
        await message.delete()



@router.edited_message(HasUrlFilter(),NotModerator())
async def telegraph_message_handler(message: types.Message):
    bot = message.bot
    for entity in message.entities:
        if entity.type == 'url' and message.text:
            url = message.text[entity.offset:entity.offset + entity.length]
        elif entity.type == 'text_link' and hasattr(entity, 'url'):
            url = entity.url
        else:
            continue
        if url and url.startswith('http'):
            await bot.forward_message(chat_id=MOD_CHAT_ID, from_chat_id=message.chat.id, message_id=message.message_id)
            await bot.send_message(MOD_CHAT_ID,f"Сообщение от {message.from_user.id} содержит скрытую ссылку")
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            break
    if 'http' in message.text or 't.me' in message.text:
        await message.bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
        await message.bot.send_message(MOD_CHAT_ID, f"Подозрительная ссылка от {message.from_user.id}")
        await message.bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(HasInlineMarkup(),NotModerator())
async def handle_inline_markup_message(message: types.Message):
    await message.bot.forward_message(chat_id=MOD_CHAT_ID, from_chat_id=message.chat.id, message_id=message.message_id)
    await message.bot.send_message(MOD_CHAT_ID, f"Сообщение от {message.from_user.id} содержит inline-кнопки")
    await message.delete()

@router.edited_message(F.content_type == ContentType.TEXT, TextModelFilter(),NotModerator())
async def handle_text(message: types.Message, text_model):
    result = await process_text(text_model, message.text)
    if result['toxicity'] > TOXICITY_THRESHOLD_TEXT:
        await handle_violation(message, 'toxic_text', message.text)
        await message.bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(F.content_type == ContentType.PHOTO, TextModelFilter(),NotModerator())
async def handle_photo(message: types.Message, text_model):
    bot = message.bot
    file = await message.bot.get_file(message.photo[-1].file_id)
    result_photo = await process_photo(bot, text_model, file)
    violation_found = False
    if result_photo['is_violation']:
        await handle_violation(message, result_photo['violation_type'], result_photo['content'])
        violation_found = True
    if message.caption:
        result_caption = await process_text(text_model, message.caption)
        if result_caption['toxicity'] > TOXICITY_THRESHOLD_TEXT:
            await handle_violation(message, 'toxic_caption', message.caption)
            violation_found = True
        if 'http' in message.caption or 't.me' in message.caption:
            await message.bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
            await message.bot.send_message(MOD_CHAT_ID, f"Подозрительная ссылка в подписи от {message.from_user.id}")
            violation_found = True
    if violation_found:
        await message.bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(F.content_type == ContentType.VIDEO, TextModelFilter(),NotModerator())
async def handle_video(message: types.Message, text_model):
    bot = message.bot
    if message.caption:
        result_caption = await process_text(text_model, message.caption)
        if result_caption['toxicity'] > TOXICITY_THRESHOLD_TEXT:
            await handle_violation(message, 'toxic_caption', message.caption)
            await bot.delete_message(message.chat.id, message.message_id)
            return
        if 'http' in message.caption.lower() or 't.me' in message.caption.lower():
            await bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
            await bot.send_message(MOD_CHAT_ID, f"Подозрительная ссылка в подписи от {message.from_user.id}")
            await bot.delete_message(message.chat.id, message.message_id)
            return
    if message.video.thumb:
        thumb_file = await bot.get_file(message.video.thumb.get("file_id"))
        result_thumb = await process_photo(bot, text_model, thumb_file)
        if result_thumb['is_violation']:
            await handle_violation(message, result_thumb['violation_type'], result_thumb['content'])
            await bot.delete_message(message.chat.id, message.message_id)
            return
    try:
        file = await bot.get_file(message.video.file_id)
        result_video = await process_video(bot, text_model, file)
        if result_video['is_violation']:
            await handle_violation(message, result_video['violation_type'], result_video['content'])
            await bot.delete_message(message.chat.id, message.message_id)
    except:
        await bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
        await bot.send_message(MOD_CHAT_ID, f"Большое видео от {message.from_user.id}, требует ручной проверки")
        await bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(F.content_type == ContentType.STICKER, TextModelFilter(),NotModerator())
async def handle_sticker(message: types.Message, text_model):
    bot = message.bot
    result = await process_sticker(bot, text_model, message.sticker)
    if result['is_violation']:
        await handle_violation(message, result['violation_type'], result['content'])
        await message.bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(F.content_type == ContentType.DOCUMENT,NotModerator())
async def handle_document(message: types.Message):
    await message.bot.forward_message(MOD_CHAT_ID, message.chat.id, message.message_id)
    await message.bot.send_message(MOD_CHAT_ID, f"Подозрительный файл от {message.from_user.id}")
    await message.bot.delete_message(message.chat.id, message.message_id)

@router.edited_message(F.content_type == ContentType.ANIMATION, TextModelFilter(),NotModerator())
async def handle_animation(message: types.Message, text_model):
    bot = message.bot
    file = await bot.get_file(message.animation.file_id)
    result = await process_video(bot, text_model, file)
    if result.get('is_violation'):
        await handle_violation(message, result['violation_type'], result['content'])
        await message.delete()

@router.message(Command("ban"),IsModerator())
async def ban_command(message: types.Message):
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        response = await message.reply("Пожалуйста, ответьте на сообщение пользователя для бана.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
        return
    try:
        await message.bot.ban_chat_member(message.chat.id, target_user.id)
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO actions (user_id, action_type, start_time) VALUES (?, ?, ?)",
                       (target_user.id, 'ban', datetime.now()))
        db_conn.commit()
        response = await message.reply(f"Пользователь @{target_user.username} забанен.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
    except Exception as e:
        response= await message.reply(f"Не удалось забанить пользователя: {e}")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)

@router.message(Command("unban"),IsModerator())
async def unban_command(message: types.Message):
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif message.text_mentions:
        target_user = message.text_mentions[0]
    else:
        response = await message.reply("Пожалуйста, ответьте на сообщение пользователя или упомяните его для разбана.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target_user.id)
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO actions (user_id, action_type, start_time) VALUES (?, ?, ?)",
                       (target_user.id, 'unban', datetime.now()))
        db_conn.commit()
        response = await message.reply(f"Пользователь @{target_user.username} разбанен.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
    except Exception as e:
        response = await message.reply(f"Не удалось разбанить пользователя: {e}")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)

@router.message(Command("mute"),IsModerator())
async def mute_command(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        response = await message.reply("Использование: /mute [длительность]")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
        return
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        response = await message.reply("Пожалуйста, ответьте на сообщение пользователя для мута.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
        return
    try:
        duration = timedelta(seconds= max(60,int(parts[1])))
    except:
        duration = timedelta(seconds=60)
    until_date = datetime.now() + duration if duration else None
    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=target_user.id,
        permissions=types.ChatPermissions(can_send_messages=False),
        until_date=until_date
    )
    cursor = db_conn.cursor()
    if duration:
        end_time = datetime.now() + duration
        duration_sec = duration.total_seconds()
    else:
        end_time = None
        duration_sec = None
    cursor.execute("INSERT INTO actions (user_id, action_type, duration, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                   (target_user.id, 'mute', duration_sec, datetime.now(), end_time))
    db_conn.commit()
    if duration:
        response = await message.reply(f"Пользователь @{target_user.username} замучен на {duration}.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
    else:
        response = await message.reply(f"Пользователь @{target_user.username} замучен навсегда.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)

@router.message(Command("unmute"),IsModerator())
async def unmute_command(message: types.Message):
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        response = await message.reply("Пожалуйста, ответьте на сообщение пользователя для размута.")
        await asyncio.sleep(10)
        await message.bot.delete_message(message.chat.id, response.message_id)
        return
    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=target_user.id,
        permissions=types.ChatPermissions(can_send_messages=True)
    )
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO actions (user_id, action_type, start_time) VALUES (?, ?, ?)",
                   (target_user.id, 'unmute', datetime.now()))
    db_conn.commit()
    response = await message.reply(f"Пользователь @{target_user.username} размучен.")
    await asyncio.sleep(10)
    await message.bot.delete_message(message.chat.id, response.message_id)

def setup_handlers(dp: Router):
    dp.include_router(router)