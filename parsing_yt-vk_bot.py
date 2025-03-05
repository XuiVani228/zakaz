import os
import time
import telebot
import logging
import yt_dlp
from tqdm import tqdm
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from googleapiclient.discovery import build
from vk_api import VkApi
from vk_api.upload import VkUpload
import threading
import json
from datetime import datetime, timedelta
import requests
import shutil

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ваши токены и ID
TELEGRAM_BOT_TOKEN = '1986934859:AAHDsdXTstuqx0_UIfV2WA2DhDpxnqfAnqI'
YOUTUBE_API_KEY = "AIzaSyBFihspeJNsQzISoi_ILVKS9TekMhz1oKw"
VK_TOKEN = "vk1.a.QShLn-EByss3IKu1g2LjHMRaTujAUfXqv6leERA547PJ2eDk6a0yAq4BqBfTTWExtDa-y7YXT64uJzsm9QE_0sGoa_BRXTuMPwIzILXEmVFO0GRuMDCpwnWvjVCN_md7Llz1ZxLK-GBz5WvVw7aPdMAPvpIUH_Mq2A3aYV0O7_un1Voxf-IiySScHIaT7FwW1OsFcz7KbRiY_dFb2H0IVA"  # Замените на ваш токен
VK_GROUP_ID = "204428788"
DOWNLOAD_FOLDER = 'C:\\Users\\dadyo\\Videos\\Captures'
UPLOADED_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'uploaded')
CHECK_INTERVAL = 24 * 60 * 60  # Интервал проверки каналов (24 часа)

# Пути
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNELS_FILE = os.path.join(SCRIPT_DIR, 'channels.json')

# Создание папок
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(UPLOADED_FOLDER):
    os.makedirs(UPLOADED_FOLDER)

# Инициализация
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Опции для yt-dlp (максимальное качество + сохранение в MP4)
ydl_opts = {
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
    'format': 'bestvideo+bestaudio/best',  # Максимальное качество видео и аудио
    'merge_output_format': 'mp4',  # Сохраняем в MP4
    'noplaylist': True,
    'nocheckcertificate': True,
    'retries': 10,
    'quiet': False,
    'playlistend': 1,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    },
}

# Функция для сохранения метаданных в файл
def save_metadata_to_file(video_path, title, description, tags):
    metadata = {"title": title, "description": description, "tags": tags}
    filename = os.path.splitext(os.path.basename(video_path))[0] + ".txt"
    metadata_file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    try:
        with open(metadata_file_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        logging.info(f"Метаданные сохранены: {metadata_file_path}")
        return metadata_file_path
    except Exception as e:
        logging.error(f"Ошибка сохранения метаданных: {e}")
        return None

# Функция для получения ID канала по имени пользователя (@username)
def get_channel_id(username):
    try:
        request = youtube.search().list(
            q=username,
            type="channel",
            part="id,snippet",
            maxResults=1
        )
        response = request.execute()
        if response["items"]:
            return response["items"][0]["id"]["channelId"]
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении ID канала: {e}")
        return None

# Функция для получения ссылки на последнее видео с канала за последние 24 часа
def get_latest_video(channel_id):
    try:
        request = youtube.search().list(
            channelId=channel_id,
            part="id,snippet",
            order="date",
            maxResults=1,
        )
        response = request.execute()
        if response["items"]:
            video = response["items"][0]
            video_id = video["id"]["videoId"]
            publish_time = video["snippet"]["publishedAt"]

            # Преобразуем время публикации в объект datetime
            publish_time_dt = datetime.strptime(publish_time, "%Y-%m-%dT%H:%M:%SZ")
            current_time = datetime.utcnow()

            # Проверяем, что видео опубликовано за последние 24 часа
            if current_time - publish_time_dt <= timedelta(days=36500):  # Практически "всегда"
                return f"https://www.youtube.com/watch?v={video_id}"
            else:
                return None
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении последнего видео: {e}")
        return None

# Функция для обработки списка каналов
def process_channels():
    try:
        if not os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
            logging.info(f"Файл {CHANNELS_FILE} не найден, был создан пустой файл.")
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            channels = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка при чтении файла каналов: {e}")
        return

    for channel in channels:
        download_latest_youtube_video(channel['channel_url'])

# Функция для скачивания последнего видео с YouTube канала
def download_latest_youtube_video(channel_url):
    file_path_to_delete = None
    metadata_file = None  # Файл для хранения метаданных
    try:
        username = channel_url.split("@")[1]
        channel_id = get_channel_id(username)
        if channel_id:
            latest_video_url = get_latest_video(channel_id)
            if latest_video_url:
                logging.info(f"Ссылка на последнее видео канала {channel_url}: {latest_video_url}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(latest_video_url, download=True)
                    file_path = ydl.prepare_filename(info)
                    file_path_to_delete = file_path
                    video_title = info.get('title', 'video')
                    description = info.get('description', 'Описание отсутствует')
                    tags = info.get('tags', [])

                    # Сохраняем метаданные
                    metadata_file = save_metadata_to_file(file_path, video_title, description, tags)

                    # Загружаем видео в VK (без превью)
                    if upload_video_to_vk(file_path, metadata_file):
                        logging.info(f"Видео канала {channel_url} успешно загружено")
                    else:
                        logging.error(f"Не удалось загрузить видео канала {channel_url}")

            else:
                logging.info(f"Не удалось найти последнее видео на канале {channel_url}.")
        else:
            logging.info(f"Не удалось получить ID канала {channel_url}.")

    except Exception as e:
        logging.error(f"Ошибка при загрузке последнего видео канала {channel_url}: {e}")
    finally:
        # Удаляем файл видео и метаданных, если они есть
        if file_path_to_delete and os.path.exists(file_path_to_delete):
            os.remove(file_path_to_delete)
            logging.info(f"Видео '{file_path_to_delete}' удалено из папки.")
        if metadata_file and os.path.exists(metadata_file):
            os.remove(metadata_file)
            logging.info(f"Файл метаданных '{metadata_file}' удален.")

# Функция для сканирования папки и загрузки новых видео
def process_video_folder():
    logging.info("Начинаю проверку папки на наличие новых видео.")
    uploaded_files = set()
    while True:
        try:
            video_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if
                           f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
            new_files = [f for f in video_files if f not in uploaded_files]

            if new_files:
                logging.info(f"Найдено {len(new_files)} новых видео.")
                for video_file in tqdm(new_files, desc="Загрузка видео"):
                    video_path = os.path.join(DOWNLOAD_FOLDER, video_file)
                    metadata_file = os.path.splitext(video_path)[0] + ".txt"  # Предполагаемое имя файла метаданных

                    # Загружаем видео в VK (без превью)
                    if upload_video_to_vk(video_path, metadata_file):
                        uploaded_files.add(video_file)
                        time.sleep(10)  # Даем время освободить файл

                        try:
                            # Перемещаем видео и метаданные в папку "uploaded"
                            shutil.move(video_path, os.path.join(UPLOADED_FOLDER, video_file))
                            logging.info(f"Видео '{video_file}' перемещено в папку 'uploaded'.")
                            if os.path.exists(metadata_file):
                                shutil.move(metadata_file, os.path.join(UPLOADED_FOLDER, os.path.basename(metadata_file)))
                                logging.info(f"Метаданные '{os.path.basename(metadata_file)}' перемещены в папку 'uploaded'.")
                        except Exception as e:
                            logging.error(f"Ошибка при перемещении файлов в папку 'uploaded': {e}")
                    else:
                        logging.error(f"Не удалось загрузить видео '{video_path}'. Видео сохранено.")

            else:
                logging.info("Новых видео не найдено.")
        except Exception as e:
            logging.error(f"Ошибка при обработке папки: {e}")
        time.sleep(60 * 1)  # Задержка 1 минута

# Функция загрузки видео в VK (без превью)
def upload_video_to_vk(video_path, metadata_file=None):
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            logging.info(f"Начинаю загрузку '{video_path}' в VK, попытка {attempt + 1}")

            upload_session = VkApi(token=VK_TOKEN)
            upload = VkUpload(upload_session)
            logging.info(f"Сессия VK API создана.")

            title, description, tags = None, None, None

            # Загрузка метаданных из файла
            if metadata_file and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    title = metadata.get("title", os.path.splitext(os.path.basename(video_path))[0])
                    description = metadata.get("description", "Описание отсутствует")
                    tags = metadata.get("tags", ["Теги отсутствуют"])
                    logging.info(f"Метаданные загружены из файла: {metadata_file}")
                except Exception as e:
                    logging.error(f"Ошибка чтения файла метаданных: {e}")

            # Получение метаданных, если не были загружены из файла
            if not title or not description or not tags:
                title, description, tags = get_video_metadata(video_path)

            try:
                response = upload.video(video_file=video_path, group_id=VK_GROUP_ID, name=title, description=description)
                logging.info(f"Видео '{title}' успешно загружено.")
            except Exception as e:
                logging.error(f"Ошибка загрузки видео: {e}")
                return False

            video_link = f"https://vk.com/video-{VK_GROUP_ID}_{response['video_id']}"
            logging.info(f"Видео '{title}' загружено: {video_link}")
            return True

        except Exception as e:
            logging.error(f"Ошибка загрузки '{video_path}', попытка {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                logging.error(f"Не удалось загрузить '{video_path}'.")
                return False

            time.sleep(retry_delay)

    return False

# Функция для планирования проверки каналов
def schedule_channels_check():
    threading.Timer(CHECK_INTERVAL, schedule_channels_check).start()  # Запускаем таймер снова
    logging.info("Запланирована проверка каналов...")
    process_channels()

# ------ Функции для удаления каналов -----
def show_channels_for_deletion(chat_id):
    try:
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        if not channels:
            bot.send_message(chat_id, "Список каналов пуст.")
            return

        keyboard = InlineKeyboardMarkup()
        for i, channel in enumerate(channels):
            button = InlineKeyboardButton(text=channel['channel_url'], callback_data=f"delete_channel_{i}")
            keyboard.add(button)

        bot.send_message(chat_id, "Выберите канал для удаления:", reply_markup=keyboard)

    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка при чтении файла каналов: {e}")
        bot.send_message(chat_id, "Ошибка при чтении списка каналов.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_channel_"))
def delete_channel_callback(call):
    try:
        channel_index = int(call.data.split("_")[2])
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        if 0 <= channel_index < len(channels):
            deleted_channel_url = channels[channel_index]['channel_url']
            del channels[channel_index]

            with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
                json.dump(channels, f, indent=4, ensure_ascii=False)

            bot.send_message(call.message.chat.id, f"Канал '{deleted_channel_url}' успешно удален.")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None) #Удаляем кнопки

        else:
            bot.send_message(call.message.chat.id, "Ошибка: неверный индекс канала.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logging.error(f"Ошибка при удалении канала: {e}")
        bot.send_message(call.message.chat.id, "Ошибка при удалении канала.")

# Обработчик команды /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Привет! Бот запущен.")

# Обработчик команды /addchannel
@bot.message_handler(commands=["addchannel"])
def add_channel(message):
    try:
        channel_url = message.text.split()[1]  # Получаем URL канала из сообщения
        if not channel_url.startswith("https://www.youtube.com/@"):
            bot.reply_to(message, "Неверный формат URL канала. Используйте https://www.youtube.com/@username")
            return
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            channels = json.load(f)
        channels.append({"channel_url": channel_url})

        with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=4)

        bot.reply_to(message, f"Канал {channel_url} успешно добавлен в список.")
        process_channels()
    except (FileNotFoundError, IndexError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        bot.reply_to(message, "Ошибка при добавлении канала.")

# Обработчик команды /deletechannel
@bot.message_handler(commands=["deletechannel"])
def delete_channel(message):
    show_channels_for_deletion(message.chat.id)

# Обработчик сообщений от пользователя
@bot.message_handler(func=lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text)
def download_video(message: Message):
    url = message.text.strip()
    bot.reply_to(message, "Начинаю скачивание видео... Подождите немного.")
    file_path_to_delete = None
    metadata_file = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            file_path_to_delete = file_path
            video_title = info.get('title', 'video')
            description = info.get('description', 'Описание отсутствует')
            tags = info.get('tags', [])

            # Сохраняем метаданные
            metadata_file = save_metadata_to_file(file_path, video_title, description, tags)

            if os.path.exists(file_path):
                bot.reply_to(message, f"Видео успешно скачано: {file_path}")
                if upload_video_to_vk(file_path, metadata_file):
                    logging.info(f"Видео '{video_title}' успешно загружено в VK.")
                else:
                    logging.error(f"Не удалось загрузить видео '{video_title}' в VK.")

            else:
                bot.reply_to(message, "Ошибка: файл не найден после скачивания.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при скачивании: {e}")
    finally:
        # Удаляем файлы видео и метаданных
        if file_path_to_delete and os.path.exists(file_path_to_delete):
            os.remove(file_path_to_delete)
            logging.info(f"Видео '{file_path_to_delete}' удалено из папки.")
        if metadata_file and os.path.exists(metadata_file):
            os.remove(metadata_file)
            logging.info(f"Файл метаданных '{metadata_file}' удален.")

# Функция для планирования проверки каналов
def schedule_channels_check():
    threading.Timer(CHECK_INTERVAL, schedule_channels_check).start()  # Запускаем таймер снова
    logging.info("Запланирована проверка каналов...")
    process_channels()  # Вызов process_channels

# Обработка текста
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    if text.startswith("https://www.youtube.com/@"):
        bot.reply_to(message, "Используйте команду /addchannel для добавления каналов")
    else:
        bot.reply_to(message, "Используйте команду /addchannel для добавления каналов.")

# Запуск бота
if __name__ == '__main__':
    import threading
    print("Бот запущен...")
    # Запускаем функцию для обработки папки в отдельном потоке
    threading.Thread(target=process_video_folder, daemon=True).start()
    # Запускаем функцию для обработки каналов
    schedule_channels_check()  # Запускаем автоматическую проверку каналов
    bot.infinity_polling()
