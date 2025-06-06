from aiogram.filters import BaseFilter
from models import text_model
from aiogram.filters import Filter
from aiogram.types import Message, InlineKeyboardMarkup
from config import MODERATOR_IDS

class TextModelFilter(BaseFilter):
    async def __call__(self, *args, **kwargs) -> dict:
        return {'text_model': text_model}

class HasInlineMarkup(Filter):
    async def __call__(self, message: Message) -> bool:
        return isinstance(message.reply_markup, InlineKeyboardMarkup)

class HasUrlFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        entities = (message.entities or []) + (message.caption_entities or [])
        return any(entity.type in ['url', 'text_link'] for entity in entities)
class NotModerator(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id not in MODERATOR_IDS

class IsModerator(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in MODERATOR_IDS