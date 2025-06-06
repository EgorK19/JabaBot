from aiogram import BaseMiddleware
from aiogram.types import Message
from datetime import datetime, timedelta
from database import db_conn, handle_violation
from config import SPAM_MESSAGE_LIMIT, SPAM_TIME_WINDOW_MINUTES

class SpamDetector(BaseMiddleware):
	async def __call__(self, handler, event: Message, data: dict):
		if not isinstance(event, Message):
			return await handler(event, data)
		user_id = event.from_user.id
		cursor = db_conn.cursor()
		cursor.execute('INSERT INTO messages (user_id, message_time) VALUES (?, ?)', (user_id, datetime.now()))
		one_minute_ago = datetime.now() - timedelta(minutes=SPAM_TIME_WINDOW_MINUTES)
		cursor.execute('DELETE FROM messages WHERE message_time < ?', (one_minute_ago,))
		cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ? AND message_time >= ?',(user_id, one_minute_ago))
		message_count = cursor.fetchone()[0]
		db_conn.commit()
		if message_count > SPAM_MESSAGE_LIMIT:
			await handle_violation(event, 'spam', 'Too many messages in a short time')
			await event.delete()
			return
		return await handler(event, data)