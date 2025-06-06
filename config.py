CHAT_ID = '-1002643495581'  # ID чата для модерации
MOD_CHAT_ID = '-1002687953805'  # ID чата модераторов
BOT_TOKEN = '7737428651:AAExUTw_1ZScU2YSOkuwIaLxvrvQnmVgN8s' # токен бота
MODERATOR_IDS = [1087968824]

# Параметры обнаружения спама
SPAM_MESSAGE_LIMIT = 10
SPAM_TIME_WINDOW_MINUTES = 1

# Пороги токсичности от 0 до 1
TOXICITY_THRESHOLD_TEXT = 0.65  # Для текстовых сообщений, подписей к фото и видео
TOXICITY_THRESHOLD_MEDIA = 0.65  # Для текста, извлеченного из медиа через OCR

# Порог NSFW от 0 до 1
NSFW_THRESHOLD = 0.5

# Логирование в консоли True - логировать, False - нет
LOG = True

# Режим строгости модерации, True - для тестирования, False - строгий режим для полноценного функционирования в чате
EASY_MODE = True