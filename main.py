import telebot
import json
import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
from telebot import types

# ==================== ТАНЗИМОТ (КОНФИГУРАТСИЯ) ====================
BOT_TOKEN = "7757855093:AAHnKu13QdJB3RUfT_pNZ6HFzsBxD4ATzDI"  # Token-и ботатонро дар ин ҷо ворид кунед
ADMIN_USER_ID = 6862331593  # ID-и Telegram-и администратор (танҳо рақам)
CHANNEL_ID = "@kinohoijazob"  # ID-и канал ё username (масалан @mychannel ё -100xxxxxxxxxx)
DATA_FILE = "bot_data.json"  # Номи файли JSON барои захираи маълумот
MAX_QUEUE_SIZE = 10  # Шумораи максималии филмҳо дар навбат
DEFAULT_POST_TIME = "10:00"  # Вақти пешфарз барои интишор

# Вақти минтақавии Тоҷикистон
TAJIKISTAN_TZ = pytz.timezone('Asia/Dushanbe')

# ==================== ТАНЗИМИ LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== ИНИТСИАЛИЗАТСИЯИ БОТ ====================
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== СТРУКТУРАИ МАЪЛУМОТ ====================
class BotData:
    def __init__(self):
        self.movie_queue: List[Dict] = []  # Навбати филмҳо
        self.post_time: str = DEFAULT_POST_TIME  # Вақти интишор
        self.last_post_date: str = ""  # Таърихи охирин интишор
    
    def to_dict(self) -> Dict:
        """Табдил додани маълумот ба dict барои JSON"""
        return {
            'movie_queue': self.movie_queue,
            'post_time': self.post_time,
            'last_post_date': self.last_post_date
        }
    
    def from_dict(self, data: Dict):
        """Бор кардани маълумот аз dict"""
        self.movie_queue = data.get('movie_queue', [])
        self.post_time = data.get('post_time', DEFAULT_POST_TIME)
        self.last_post_date = data.get('last_post_date', "")

# ==================== ГЛОБАЛИИ МАЪЛУМОТ ====================
bot_data = BotData()

# ==================== ФУНКСИЯҲОИ КУМАКӢ ====================
def get_tajikistan_time() -> datetime:
    """Гирифтани вақти кунунии Тоҷикистон"""
    return datetime.now(TAJIKISTAN_TZ)

def save_data():
    """Захираи маълумот ба файли JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_data.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Маълумот бомуваффақият захира шуд")
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми захираи маълумот: {e}")

def load_data():
    """Бор кардани маълумот аз файли JSON"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        bot_data.from_dict(data)
        logger.info("Маълумот бомуваффақият бор карда шуд")
    except FileNotFoundError:
        logger.info("Файли маълумот ёфт нашуд, маълумоти нав эҷод мешавад")
        save_data()
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми бор кардани маълумот: {e}")

def is_admin(user_id: int) -> bool:
    """Санҷиши ҳуқуқи администратор"""
    return user_id == ADMIN_USER_ID

def get_next_post_time() -> tuple:
    """Гирифтани вақти интишори навбатӣ ва вақти боқимонда"""
    try:
        now = get_tajikistan_time()
        post_hour, post_minute = map(int, bot_data.post_time.split(':'))
        
        # Муайян кардани таърихи интишори навбатӣ
        next_post = now.replace(hour=post_hour, minute=post_minute, second=0, microsecond=0)
        
        # Агар вақт гузашта бошад, барои фардо муайян мекунем
        if next_post <= now:
            next_post += timedelta(days=1)
        
        # Ҳисоб кардани вақти боқимонда
        time_remaining = next_post - now
        
        # Табдил ба дақиқаҳо
        minutes_remaining = int(time_remaining.total_seconds() // 60)
        hours_remaining = minutes_remaining // 60
        minutes_remaining = minutes_remaining % 60
        
        time_str = ""
        if hours_remaining > 0:
            time_str = f"{hours_remaining} соат {minutes_remaining} дақиқа"
        else:
            time_str = f"{minutes_remaining} дақиқа"
        
        return next_post.strftime("%Y-%m-%d %H:%M"), time_str
        
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми ҳисоби вақти навбатӣ: {e}")
        return "Номуайян", "Номуайян"

def create_main_keyboard():
    """Эҷоди клавиатураи асосӣ"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Сафи якум - маълумоти асосӣ
    status_btn = types.InlineKeyboardButton("📊 Вазъият", callback_data="status")
    queue_btn = types.InlineKeyboardButton("📝 Рӯйхати филмҳо", callback_data="listmovies")
    keyboard.row(status_btn, queue_btn)
    
    # Сафи дуюм - идоракунӣ
    time_btn = types.InlineKeyboardButton("⏰ Тағири вақт", callback_data="settime")
    post_btn = types.InlineKeyboardButton("🚀 Интишори форӣ", callback_data="forcepost")
    keyboard.row(time_btn, post_btn)
    
    # Сафи сеюм - дигар амалҳо
    remove_btn = types.InlineKeyboardButton("🗑️ Нест кардан", callback_data="remove")
    refresh_btn = types.InlineKeyboardButton("🔄 Навсозӣ", callback_data="refresh")
    keyboard.row(remove_btn, refresh_btn)
    
    return keyboard

def create_remove_keyboard():
    """Эҷоди клавиатураи нест кардани филмҳо"""
    if not bot_data.movie_queue:
        return None
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопкаҳо барои ҳар филм
    for i, movie in enumerate(bot_data.movie_queue):
        caption = movie.get('caption', f'Филм #{i+1}')
        if len(caption) > 25:
            caption = caption[:22] + "..."
        
        btn = types.InlineKeyboardButton(
            f"{i+1}. {caption}", 
            callback_data=f"remove_{i}"
        )
        keyboard.add(btn)
    
    # Кнопкаи бозгашт
    back_btn = types.InlineKeyboardButton("⬅️ Бозгашт", callback_data="back_to_main")
    keyboard.add(back_btn)
    
    return keyboard

def create_time_keyboard():
    """Эҷоди клавиатураи интихоби вақт"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    # Вақтҳои пешниҳодшуда
    times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
    
    buttons = []
    for time_str in times:
        btn = types.InlineKeyboardButton(time_str, callback_data=f"settime_{time_str}")
        buttons.append(btn)
    
    # Ҷуфт кардани кнопкаҳо
    for i in range(0, len(buttons), 3):
        row = buttons[i:i+3]
        keyboard.row(*row)
    
    # Кнопкаи бозгашт
    back_btn = types.InlineKeyboardButton("⬅️ Бозгашт", callback_data="back_to_main")
    keyboard.add(back_btn)
    
    return keyboard

def post_movie():
    """Интишори филми навбатӣ дар канал"""
    try:
        if not bot_data.movie_queue:
            logger.info("Навбати филмҳо холӣ аст")
            return
        
        # Гирифтани филми аввал аз навбат
        movie = bot_data.movie_queue.pop(0)
        
        # Интишори филм дар канал
        bot.send_video(
            chat_id=CHANNEL_ID,
            video=movie['file_id'],
            caption=movie.get('caption', ''),
            parse_mode='HTML'
        )
        
        # Навсозии таърихи охирин интишор
        bot_data.last_post_date = get_tajikistan_time().strftime("%Y-%m-%d")
        
        # Захираи маълумот
        save_data()
        
        logger.info(f"Филм бомуваффақият интишор шуд: {movie.get('caption', 'Бе сарлавҳа')}")
        
        # Огоҳ кардани администратор
        try:
            next_time, remaining_time = get_next_post_time()
            bot.send_message(
                ADMIN_USER_ID,
                f"✅ Филм бомуваффақият интишор шуд!\n\n"
                f"📝 Сарлавҳа: {movie.get('caption', 'Бе сарлавҳа')}\n"
                f"⏰ Вақт: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 Филмҳои боқимонда дар навбат: {len(bot_data.movie_queue)}\n"
                f"🕐 Интишори навбатӣ: {remaining_time} дигар",
                reply_markup=create_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Хатогӣ ҳангоми огоҳкунии администратор: {e}")
            
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми интишори филм: {e}")
        try:
            bot.send_message(
                ADMIN_USER_ID,
                f"❌ Хатогӣ ҳангоми интишори филм: {str(e)}",
                reply_markup=create_main_keyboard()
            )
        except:
            pass

def setup_scheduler():
    """Танзими ҷадвали интишор"""
    schedule.clear()  # Пок кардани ҷадвали қаблӣ
    schedule.every().day.at(bot_data.post_time).do(post_movie)
    logger.info(f"Ҷадвали интишор танзим шуд барои соати {bot_data.post_time}")

def scheduler_thread():
    """Thread барои кори ҷадвал"""
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Санҷиш ҳар дақиқа
        except Exception as e:
            logger.error(f"Хатогӣ дар scheduler thread: {e}")
            time.sleep(60)

# ==================== ФАРМОНҲОИ БОТ ====================

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """Коркарди фармони /start ва /help"""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Шумо ҳуқуқи истифодаи ин ботро надоред.")
        return
    
    next_time, remaining_time = get_next_post_time()
    
    help_text = f"""
🎬 **Боти интишори филмҳо**

**Вазъи кунунӣ:**
🎭 Филмҳо дар навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}

**Дастурамал:**
• Барои илова кардани филм - файли видеоро фиристед
• Барои идоракунӣ аз кнопкаҳои зерин истифода баред

**Хусусиятҳо:**
✅ Интишори худкор ҳар рӯз
✅ Идоракунӣ бо кнопкаҳо
✅ Вақти Тоҷикистон
✅ Нишондодани вақти боқимонда
    """
    
    bot.reply_to(message, help_text, parse_mode='Markdown', reply_markup=create_main_keyboard())
    logger.info(f"Администратор фармони help-ро дархост кард")

# ==================== КОРКАРДИ CALLBACK-ҲО ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """Коркарди ҳамаи callback-ҳо"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Шумо ҳуқуқи дастрасӣ надоред!")
        return
    
    try:
        if call.data == "status":
            handle_status_callback(call)
        elif call.data == "listmovies":
            handle_list_movies_callback(call)
        elif call.data == "settime":
            handle_settime_callback(call)
        elif call.data.startswith("settime_"):
            handle_settime_specific_callback(call)
        elif call.data == "forcepost":
            handle_forcepost_callback(call)
        elif call.data == "remove":
            handle_remove_callback(call)
        elif call.data.startswith("remove_"):
            handle_remove_specific_callback(call)
        elif call.data == "refresh":
            handle_refresh_callback(call)
        elif call.data == "back_to_main":
            handle_back_to_main_callback(call)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Хатогӣ дар callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ Хатогӣ рӯй дод!")

def handle_status_callback(call):
    """Коркарди callback-и status"""
    queue_count = len(bot_data.movie_queue)
    next_movie = bot_data.movie_queue[0]['caption'] if bot_data.movie_queue else "Ҳеҷ филм дар навбат нест"
    next_time, remaining_time = get_next_post_time()
    
    status_text = f"""
📊 **Вазъи кунунӣ:**

🎬 Филмҳо дар навбат: {queue_count}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}
🎭 Филми навбатӣ: {next_movie[:50]}{'...' if len(next_movie) > 50 else ''}
📅 Охирин интишор: {bot_data.last_post_date if bot_data.last_post_date else 'Ҳанӯз интишор нашудааст'}
🕒 Вақти кунунӣ: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M')}
    """
    
    bot.edit_message_text(
        status_text, 
        call.message.chat.id, 
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def handle_list_movies_callback(call):
    """Коркарди callback-и listmovies"""
    if not bot_data.movie_queue:
        bot.edit_message_text(
            "📝 **Навбати филмҳо холӣ аст.**\n\nБарои илова кардани филм, файли видеоро фиристед.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    movies_text = "📝 **Рӯйхати филмҳо дар навбат:**\n\n"
    for i, movie in enumerate(bot_data.movie_queue, 1):
        caption = movie.get('caption', 'Бе сарлавҳа')
        added_date = movie.get('added_date', 'Номаълум')
        movies_text += f"{i}. {caption}\n   📅 {added_date}\n\n"
    
    # Илова кардани маълумот дар бораи интишори навбатӣ
    next_time, remaining_time = get_next_post_time()
    movies_text += f"🕐 Интишори навбатӣ: {remaining_time} дигар"
    
    bot.edit_message_text(
        movies_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def handle_settime_callback(call):
    """Коркарди callback-и settime"""
    bot.edit_message_text(
        f"⏰ **Интихоби вақти интишор**\n\nВақти кунунӣ: {bot_data.post_time}\n\nВақти дилхоҳро интихоб кунед:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_time_keyboard()
    )

def handle_settime_specific_callback(call):
    """Коркарди callback-и танзими вақти мушаххас"""
    new_time = call.data.split("_")[1]
    
    try:
        # Санҷиши формати вақт
        time_parts = new_time.split(':')
        hour, minute = int(time_parts[0]), int(time_parts[1])
        
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ValueError("Вақти нодуруст")
        
        # Танзими вақти нав
        bot_data.post_time = new_time
        setup_scheduler()
        save_data()
        
        next_time, remaining_time = get_next_post_time()
        
        bot.edit_message_text(
            f"✅ **Вақти интишор тағир дода шуд!**\n\n"
            f"🕐 Вақти нав: {new_time}\n"
            f"⏰ То интишори навбатӣ: {remaining_time}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        logger.info(f"Вақти интишор тағир дода шуд ба: {new_time}")
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ **Хатогӣ ҳангоми тағири вақт**\n\n{str(e)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

def handle_forcepost_callback(call):
    """Коркарди callback-и forcepost"""
    if not bot_data.movie_queue:
        bot.edit_message_text(
            "❌ **Навбати филмҳо холӣ аст**\n\nБарои интишор ягон филм мавҷуд нест.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    bot.edit_message_text(
        f"⏳ **Интишори филм...**\n\nФилм: {bot_data.movie_queue[0].get('caption', 'Бе сарлавҳа')}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    post_movie()
    logger.info("Администратор интишори форӣ дархост кард")

def handle_remove_callback(call):
    """Коркарди callback-и remove"""
    if not bot_data.movie_queue:
        bot.edit_message_text(
            "📝 **Навбати филмҳо холӣ аст**\n\nҲеҷ филм барои нест кардан мавҷуд нест.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    bot.edit_message_text(
        "🗑️ **Интихоби филм барои нест кардан**\n\nФилми дилхоҳро интихоб кунед:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_remove_keyboard()
    )

def handle_remove_specific_callback(call):
    """Коркарди callback-и нест кардани филми мушаххас"""
    try:
        movie_index = int(call.data.split("_")[1])
        
        if movie_index < 0 or movie_index >= len(bot_data.movie_queue):
            bot.edit_message_text(
                "❌ **Филм ёфт нашуд**\n\nФилми интихобшуда дар навбат мавҷуд нест.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            return
        
        removed_movie = bot_data.movie_queue.pop(movie_index)
        save_data()
        
        bot.edit_message_text(
            f"✅ **Филм нест карда шуд**\n\n"
            f"📝 {removed_movie.get('caption', 'Бе сарлавҳа')}\n\n"
            f"📊 Филмҳои боқимонда: {len(bot_data.movie_queue)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        logger.info(f"Филм аз навбат нест карда шуд: {removed_movie.get('caption', 'Бе сарлавҳа')}")
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ **Хатогӣ ҳангоми нест кардан**\n\n{str(e)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

def handle_refresh_callback(call):
    """Коркарди callback-и refresh"""
    next_time, remaining_time = get_next_post_time()
    
    refresh_text = f"""
🔄 **Маълумот навсозӣ шуд**

📊 Филмҳо дар навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}
🕒 Вақти кунунӣ: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M')}

Барои идоракунӣ аз кнопкаҳо истифода баред.
    """
    
    bot.edit_message_text(
        refresh_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def handle_back_to_main_callback(call):
    """Коркарди callback-и бозгашт ба меню"""
    next_time, remaining_time = get_next_post_time()
    
    main_text = f"""
🎬 **Боти интишори филмҳо**

📊 Филмҳо дар навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}

Барои идоракунӣ аз кнопкаҳои зер истифода баред:
    """
    
    bot.edit_message_text(
        main_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

# ==================== КОРКАРДИ ФАЙЛҲОИ ВИДЕОӢ ====================

@bot.message_handler(content_types=['video'])
def handle_video(message):
    """Коркарди файлҳои видеоӣ"""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Шумо ҳуқуқи истифодаи ин ботро надоред.")
        return
    
    try:
        # Санҷиши ҷои холӣ дар навбат
        if len(bot_data.movie_queue) >= MAX_QUEUE_SIZE:
            bot.reply_to(
                message, 
                f"❌ **Навбат пур аст!**\n\n"
                f"Ҳадди аксар: {MAX_QUEUE_SIZE} филм\n"
                f"Лутфан якчанд филмро нест кунед.",
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            return
        
        # Илова кардани филм ба навбат
        movie_data = {
            'file_id': message.video.file_id,
            'caption': message.caption or 'Бе сарлавҳа',
            'file_name': message.video.file_name or 'video.mp4',
            'file_size': message.video.file_size,
            'duration': message.video.duration,
            'added_date': get_tajikistan_time().strftime('%Y-%m-%d %H:%M'),
            'added_by': message.from_user.id
        }
        
        bot_data.movie_queue.append(movie_data)
        save_data()
        
        # Пайёми тасдиқ
        next_time, remaining_time = get_next_post_time()
        
        confirmation_text = f"""
✅ **Филм ба навбат илова шуд!**

📝 Сарлавҳа: {movie_data['caption']}
📁 Файл: {movie_data['file_name']}
📊 Мақоми навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
📅 Санаи илова: {movie_data['added_date']}

⏰ Интишори навбатӣ: {remaining_time} дигар
        """
        
        bot.reply_to(
            message, 
            confirmation_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        logger.info(f"Филми нав илова шуд: {movie_data['caption']}")
        
    except Exception as e:
        error_text = f"❌ **Хатогӣ ҳангоми илова кардани филм**\n\n{str(e)}"
        bot.reply_to(message, error_text, parse_mode='Markdown')
        logger.error(f"Хатогӣ ҳангоми илова кардани филм: {e}")

# ==================== КОРКАРДИ ДИГАР НАВЪҲОИ ПАЁМҲО ====================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Коркарди ҳуҷҷатҳо"""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Шумо ҳуқуқи истифодаи ин ботро надоред.")
        return
    
    # Санҷиш оё ҳуҷҷат видео аст
    if message.document.mime_type and message.document.mime_type.startswith('video/'):
        try:
            # Санҷиши ҷои холӣ дар навбат
            if len(bot_data.movie_queue) >= MAX_QUEUE_SIZE:
                bot.reply_to(
                    message, 
                    f"❌ **Навбат пур аст!**\n\n"
                    f"Ҳадди аксар: {MAX_QUEUE_SIZE} филм\n"
                    f"Лутфан якчанд филмро нест кунед.",
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
                return
            
            # Илова кардани видео-ҳуҷҷат ба навбат
            movie_data = {
                'file_id': message.document.file_id,
                'caption': message.caption or message.document.file_name or 'Бе сарлавҳа',
                'file_name': message.document.file_name or 'video.mp4',
                'file_size': message.document.file_size,
                'duration': 0,  # Барои ҳуҷҷатҳо давомнокӣ дастрас нест
                'added_date': get_tajikistan_time().strftime('%Y-%m-%d %H:%M'),
                'added_by': message.from_user.id,
                'type': 'document'
            }
            
            bot_data.movie_queue.append(movie_data)
            save_data()
            
            # Пайёми тасдиқ
            next_time, remaining_time = get_next_post_time()
            
            confirmation_text = f"""
✅ **Видео-ҳуҷҷат ба навбат илова шуд!**

📝 Сарлавҳа: {movie_data['caption']}
📁 Файл: {movie_data['file_name']}
📊 Мақоми навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
📅 Санаи илова: {movie_data['added_date']}

⏰ Интишори навбатӣ: {remaining_time} дигар
            """
            
            bot.reply_to(
                message, 
                confirmation_text,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            
            logger.info(f"Видео-ҳуҷҷат илова шуд: {movie_data['caption']}")
            
        except Exception as e:
            error_text = f"❌ **Хатогӣ ҳангоми илова кардани ҳуҷҷат**\n\n{str(e)}"
            bot.reply_to(message, error_text, parse_mode='Markdown')
            logger.error(f"Хатогӣ ҳангоми илова кардани ҳуҷҷат: {e}")
    else:
        bot.reply_to(
            message, 
            "❌ **Навъи файли дастгиринашуда**\n\n"
            "Лутфан танҳо файлҳои видеоиро фиристед.",
            parse_mode='Markdown'
        )

@bot.message_handler(content_types=['photo', 'audio', 'voice', 'animation', 'sticker'])
def handle_unsupported_media(message):
    """Коркарди медиафайлҳои дастгиринашуда"""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Шумо ҳуқуқи истифодаи ин ботро надоред.")
        return
    
    media_types = {
        'photo': 'акс',
        'audio': 'аудио',
        'voice': 'овозӣ паём',
        'animation': 'GIF',
        'sticker': 'стикер'
    }
    
    media_type = media_types.get(message.content_type, 'медиафайл')
    
    bot.reply_to(
        message,
        f"❌ **Навъи файли дастгиринашуда**\n\n"
        f"Шумо {media_type} фиристодед.\n"
        f"Ин бот танҳо файлҳои видеоиро қабул мекунад.\n\n"
        f"Лутфан файли видеоро фиристед.",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    """Коркарди паёмҳои матнӣ"""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Шумо ҳуқуқи истифодаи ин ботро надоред.")
        return
    
    # Санҷиши фармонҳои махфӣ
    text = message.text.lower().strip()
    
    if text in ['/status', 'статус', 'вазъият']:
        # Нишон додани вазъияти муфассал
        queue_count = len(bot_data.movie_queue)
        next_time, remaining_time = get_next_post_time()
        
        status_text = f"""
📊 **Вазъи муфассал:**

🎬 Филмҳо дар навбат: {queue_count}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}
📅 Охирин интишор: {bot_data.last_post_date if bot_data.last_post_date else 'Ҳанӯз интишор нашудааст'}
🕒 Вақти кунунӣ: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M')}
🆔 Канал: {CHANNEL_ID}

**Филмҳои дар навбат:**
        """
        
        if bot_data.movie_queue:
            for i, movie in enumerate(bot_data.movie_queue[:5], 1):  # Танҳо 5-тои аввал
                status_text += f"\n{i}. {movie.get('caption', 'Бе сарлавҳа')[:30]}..."
            
            if len(bot_data.movie_queue) > 5:
                status_text += f"\n... ва {len(bot_data.movie_queue) - 5} филми дигар"
        else:
            status_text += "\nҲеҷ филм дар навбат нест"
        
        bot.reply_to(message, status_text, parse_mode='Markdown', reply_markup=create_main_keyboard())
        
    elif text in ['/clear', 'пок кардан', 'очистить']:
        # Пок кардани навбат (бо тасдиқ)
        if bot_data.movie_queue:
            bot.reply_to(
                message,
                f"⚠️ **Огоҳӣ!**\n\n"
                f"Шумо мехоҳед {len(bot_data.movie_queue)} филмро аз навбат нест кунед?\n"
                f"Барои тасдиқ '/clearconfirm' нависед.",
                parse_mode='Markdown'
            )
        else:
            bot.reply_to(message, "📝 Навбат аллакай холӣ аст.", reply_markup=create_main_keyboard())
    
    elif text in ['/clearconfirm', 'тасдиқ']:
        # Тасдиқи пок кардани навбат
        cleared_count = len(bot_data.movie_queue)
        bot_data.movie_queue.clear()
        save_data()
        
        bot.reply_to(
            message,
            f"✅ **Навбат пок карда шуд!**\n\n"
            f"🗑️ {cleared_count} филм нест карда шуд.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        logger.info(f"Навбати филмҳо пок карда шуд: {cleared_count} филм")
    
    elif text.startswith('/settime '):
        # Танзими вақт бо фармон
        try:
            new_time = text.split(' ', 1)[1].strip()
            
            # Санҷиши формати вақт
            time_parts = new_time.split(':')
            if len(time_parts) != 2:
                raise ValueError("Формати нодуруст")
            
            hour, minute = int(time_parts[0]), int(time_parts[1])
            
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError("Вақти нодуруст")
            
            # Танзими вақти нав
            bot_data.post_time = new_time
            setup_scheduler()
            save_data()
            
            next_time, remaining_time = get_next_post_time()
            
            bot.reply_to(
                message,
                f"✅ **Вақти интишор тағир дода шуд!**\n\n"
                f"🕐 Вақти нав: {new_time}\n"
                f"⏰ То интишори навбатӣ: {remaining_time}",
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            
            logger.info(f"Вақти интишор тағир дода шуд ба: {new_time}")
            
        except (IndexError, ValueError) as e:
            bot.reply_to(
                message,
                "❌ **Формати нодуруст!**\n\n"
                "Истифода: `/settime 14:30`\n"
                "Мисол: `/settime 20:00`",
                parse_mode='Markdown'
            )
    
    elif text in ['/backup', 'захира', 'бэкап']:
        # Эҷоди нусхаи захиравӣ
        try:
            backup_data = {
                'backup_date': get_tajikistan_time().strftime('%Y-%m-%d %H:%M:%S'),
                'version': '1.0',
                'data': bot_data.to_dict()
            }
            
            backup_text = json.dumps(backup_data, ensure_ascii=False, indent=2)
            
            # Фиристодани бекап ҳамчун файл
            bot.send_document(
                message.chat.id,
                telebot.types.InputFile.from_string(
                    backup_text.encode('utf-8'),
                    f"bot_backup_{get_tajikistan_time().strftime('%Y%m%d_%H%M%S')}.json"
                ),
                caption=f"💾 **Нусхаи захиравӣ**\n\n"
                        f"📅 Санаи эҷод: {backup_data['backup_date']}\n"
                        f"📊 Филмҳо: {len(bot_data.movie_queue)}",
                parse_mode='Markdown'
            )
            
            logger.info("Нусхаи захиравӣ эҷод карда шуд")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Хатогӣ ҳангоми эҷоди бекап: {str(e)}")
    
    else:
        # Пайёми умумӣ барои паёмҳои номаълум
        bot.reply_to(
            message,
            "ℹ️ **Дастурамал:**\n\n"
            "• Барои илова кардани филм - файли видеоро фиристед\n"
            "• Барои идоракунӣ - аз кнопкаҳо истифода баред\n"
            "• Барои кӯмак - `/help` нависед\n\n"
            "**Фармонҳои иловагӣ:**\n"
            "• `/status` - вазъияти муфассал\n"
            "• `/settime 14:30` - танзими вақт\n"
            "• `/clear` - пок кардани навбат\n"
            "• `/backup` - эҷоди нусхаи захиравӣ",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

# ==================== КОРКАРДИ ХАТОГИҲО ====================

def error_handler(func):
    """Decorator барои коркарди хатогиҳо"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Хатогӣ дар {func.__name__}: {e}")
            try:
                if args and hasattr(args[0], 'message'):
                    bot.send_message(
                        ADMIN_USER_ID,
                        f"❌ **Хатогии системавӣ**\n\n"
                        f"Функция: {func.__name__}\n"
                        f"Хатогӣ: {str(e)}\n"
                        f"Вақт: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M:%S')}",
                        parse_mode='Markdown'
                    )
            except:
                pass
    return wrapper

# ==================== ФУНКСИЯҲОИ ХИЗМАТРАСОНӢ ====================

def check_bot_health():
    """Санҷиши саломатии бот"""
    try:
        bot_info = bot.get_me()
        logger.info(f"Бот кор мекунад: @{bot_info.username}")
        
        # Санҷиши дастрасии канал
        try:
            channel_info = bot.get_chat(CHANNEL_ID)
            logger.info(f"Канал дастрас аст: {channel_info.title}")
        except Exception as e:
            logger.error(f"Хатогӣ дар дастрасӣ ба канал: {e}")
            bot.send_message(
                ADMIN_USER_ID,
                f"⚠️ **Огоҳӣ!**\n\n"
                f"Бот ба канал {CHANNEL_ID} дастрасӣ надорад.\n"
                f"Хатогӣ: {str(e)}",
                parse_mode='Markdown'
            )
        
        return True
    except Exception as e:
        logger.error(f"Хатогӣ дар санҷиши саломатии бот: {e}")
        return False

def send_daily_report():
    """Фиристодани ҳисоботи рӯзона"""
    try:
        today = get_tajikistan_time().strftime('%Y-%m-%d')
        
        report_text = f"""
📋 **Ҳисоботи рӯзона - {today}**

📊 **Омор:**
🎬 Филмҳо дар навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
📅 Охирин интишор: {bot_data.last_post_date if bot_data.last_post_date else 'Ҳанӯз интишор нашудааст'}

📈 **Вазъият:**
{'✅ Ҳама чиз хуб кор мекунад' if bot_data.movie_queue else '⚠️ Навбати филмҳо холӣ аст'}

⏰ Ҳисобот аз: {get_tajikistan_time().strftime('%H:%M')}
        """
        
        bot.send_message(
            ADMIN_USER_ID,
            report_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        logger.info("Ҳисоботи рӯзона фиристода шуд")
        
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми фиристодани ҳисобот: {e}")

def setup_daily_report():
    """Танзими ҳисоботи рӯзона"""
    schedule.every().day.at("09:00").do(send_daily_report)
    logger.info("Ҳисоботи рӯзона танзим шуд барои соати 09:00")

# ==================== ФУНКСИЯИ АСОСӢ ====================

def main():
    """Функсияи асосии бот"""
    try:
        logger.info("Бот оғоз ёфт...")
        
        # Бор кардани маълумот
        load_data()
        
        # Танзими ҷадвал
        setup_scheduler()
        setup_daily_report()
        
        # Санҷиши саломатии бот
        if not check_bot_health():
            logger.error("Хатогӣ дар санҷиши саломатии бот")
            return
        
        # Оғози thread барои ҷадвал
        scheduler_thread_obj = threading.Thread(target=scheduler_thread, daemon=True)
        scheduler_thread_obj.start()
        logger.info("Thread-и ҷадвал оғоз ёфт")
        
        # Пайёми оғози кор ба администратор
        try:
            next_time, remaining_time = get_next_post_time()
            start_message = f"""
🚀 **Бот бомуваффақият оғоз ёфт!**

📊 **Вазъияти кунунӣ:**
🎬 Филмҳо дар навбат: {len(bot_data.movie_queue)}/{MAX_QUEUE_SIZE}
⏰ Вақти интишор: {bot_data.post_time}
🕐 То интишори навбатӣ: {remaining_time}
🕒 Вақти оғоз: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M:%S')}

✅ Ҳама системаҳо омода
            """
            
            bot.send_message(
                ADMIN_USER_ID,
                start_message,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Хатогӣ ҳангоми фиристодани пайёми оғоз: {e}")
        
        logger.info("Бот омода ба кор. Интизори паёмҳо...")
        
        # Оғози polling
        bot.infinity_polling(
            timeout=20,
            long_polling_timeout=20,
            none_stop=True,
            interval=1
        )
        
    except KeyboardInterrupt:
        logger.info("Бот аз ҷониби корбар қатъ карда шуд")
    except Exception as e:
        logger.error(f"Хатогии ҷиддӣ дар кори бот: {e}")
        try:
            bot.send_message(
                ADMIN_USER_ID,
                f"❌ **Хатогии ҷиддӣ!**\n\n"
                f"Бот қатъ шуд: {str(e)}\n"
                f"Вақт: {get_tajikistan_time().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode='Markdown'
            )
        except:
            pass
        raise
    finally:
        logger.info("Бот хомӯш шуд")

# ==================== НУҚТАИ ВОРИДШАВӢ ====================

if __name__ == "__main__":
    main()