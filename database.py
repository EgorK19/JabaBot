import sqlite3
from datetime import datetime, timedelta
from aiogram import types
from config import CHAT_ID, EASY_MODE

db_conn = sqlite3.connect('moderation.db')
cursor = db_conn.cursor()


cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    last_violation_time TIMESTAMP
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS violations (
                    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    violation_type TEXT,
                    violation_time TIMESTAMP,
                    message_id INTEGER,
                    content TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    duration INTEGER,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')


cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_time TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')



db_conn.commit()

async def handle_violation(message: types.Message, violation_type: str, content: str):
    user_id = message.from_user.id
    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?,?, ?)',
                       (user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name))

        last_violation_time = None
    else:
        last_violation_time = user[4]
    cursor.execute('INSERT INTO violations (user_id, violation_type, violation_time, message_id, content) VALUES (?, ?, ?, ?, ?)',
                   (user_id, violation_type, datetime.now(), message.message_id, content))

    cursor.execute('UPDATE users SET last_violation_time = ? WHERE user_id = ?',
                   (datetime.now(), user_id))
    db_conn.commit()
    time_since_last = (datetime.now() - datetime.strptime(last_violation_time, "%Y-%m-%d %H:%M:%S.%f")).total_seconds() if last_violation_time else float('inf')
    action, duration = calculate_penalty(violation_type, time_since_last)
    if action == 'mute':
        until = datetime.now() + timedelta(seconds=duration)
        await message.bot.restrict_chat_member(CHAT_ID, user_id, until_date=int(until.timestamp()),
                                              permissions=types.ChatPermissions(can_send_messages=False))
        cursor.execute('INSERT INTO actions (user_id, action_type, duration, start_time, end_time) VALUES (?, ?, ?, ?, ?)',
                       (user_id, 'mute', duration, datetime.now(), until))
    elif action == 'ban':
        await message.bot.ban_chat_member(CHAT_ID, user_id)
        cursor.execute('INSERT INTO actions (user_id, action_type, start_time) VALUES (?, ?, ?)',
                       (user_id, 'ban', datetime.now()))
    db_conn.commit()

if EASY_MODE:
    def calculate_penalty(violation_type: str, time_since_last: float) -> tuple:
        if violation_type == 'spam':
            if time_since_last < 60:
                return 'mute', 60
            return 'mute', 60
        if violation_type in ['toxic_text', 'toxic_caption', 'toxic_image_text', 'toxic_video_text', 'toxic_sticker_text']:
            if time_since_last < 60:
                return 'mute', 60
            return 'mute', 60
        if violation_type in ['nsfw_image', 'nsfw_video', 'nsfw_sticker']:
            return 'mute', 60
        return 'warn', None
else:
    def calculate_penalty(violation_type: str, time_since_last: float) -> tuple:
        if violation_type == 'spam':
            if time_since_last < 60:
                return 'mute', 300
            return 'mute', 60
        if violation_type in ['toxic_text', 'toxic_caption', 'toxic_image_text', 'toxic_video_text', 'toxic_sticker_text']:
            if time_since_last < 60:
                return 'mute', 300
            return 'mute', 60
        if violation_type in ['nsfw_image', 'nsfw_video', 'nsfw_sticker']:
            return 'mute', 3600
        return 'warn', None

