import os
import time
import telebot
import logging
import yt_dlp
from tqdm import tqdm
from telebot.types import Message
from googleapiclient.discovery import build
from vk_api import VkApi
from vk_api.upload import VkUpload
import threading
import json
import random
from datetime import datetime, timedelta
import requests
from io import BytesIO

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Создаём бота с вашим токеном
TELEGRAM_BOT_TOKEN = '1986934859:AAHDsdXTstuqx0_UIfV2WA2DhDpxnqfAnqI'
YOUTUBE_API_KEY = "AIzaSyBFihspeJNsQzISoi_ILVKS9TekMhz1oKw"
VK_TOKEN = "vk1.a.syIRMc2Kpcj0KydWMc4E6yKHPYp1a9jbBjTDysjmFtfHKt3FUH3-DZNpecoqOaqKUMrjH8wxF3DO2pGT_ICyTSEnp4tRBE3WXQCS7L1G4CcanCwDBQ3sSwIM4FxpJO-O7nS9q0oVaH_pcHwahem3oz_Iob395shZ8SsK5BSOMHrKLDXCj9cueAaH_Fcn3qMJNN_o643JqqhQa_8oyOzMyA"
VK_GROUP_ID = "204428788"
DOWNLOAD_FOLDER = 'C:\\Users\\dadyo\\Videos\\Captures'
CHECK_INTERVAL = 24 * 60 * 60  # 24 часа в секундах

# Получаем путь к текущему скрипту
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNELS_FILE = os.path.join(SCRIPT_DIR, 'channels.json')

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Указываем папку для сохранения видео
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Опции для yt-dlp
ydl_opts = {
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
    'format': 'mp4',
    'noplaylist': True,
    'nocheckcertificate': True,
    'retries': 100000000000000000000,
    'quiet': False,
    'playlistend': 1,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
}


# Функция получения метаданных видео (позднее извлечение)
def get_video_metadata(video_path):
    try:
        if video_path.startswith('http'):
             with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_path, download=False)
             title = info_dict.get('title', os.path.basename(video_path))
             description = info_dict.get('description', "Описание отсутствует")
             thumbnail = info_dict.get('thumbnails', [{}])[-1].get('url')
             tags = info_dict.get('tags', ["Теги отсутствуют"])
             return title, description, thumbnail, tags
        else:
            title = os.path.basename(video_path)
            description = "Описание отсутствует"
            thumbnail = None
            tags = ["Теги отсутствуют"]
            return title, description, thumbnail, tags
    except Exception as e:
        logging.error(f"Ошибка при получении метаданных: {e}")
        return os.path.basename(video_path), "Описание отсутствует", None, ["Теги отсутствуют"]


# Функция загрузки видео на VK
def upload_video_to_vk(video_path):
    max_retries = 3  # Максимальное количество попыток загрузки
    retry_delay = 5  # Задержка перед повторной попыткой (секунды)
    for attempt in range(max_retries):
        try:
            logging.info(f"Начинаю загрузку видео '{video_path}' в VK, попытка {attempt + 1}")

            upload_session = VkApi(token=VK_TOKEN)
            upload = VkUpload(upload_session)
            logging.info(f"Сессия VK API и VkUpload создана.")

            title, description, thumbnail, tags = get_video_metadata(video_path)

            if thumbnail:
                try:
                    logging.info(f"Загрузка превью для '{video_path}'.")
                    response = requests.get(thumbnail, stream=True)
                    response.raise_for_status()
                    image_file = BytesIO(response.content)
                    photo = upload.photo_video(image_file, group_id=VK_GROUP_ID)
                    photo_id = f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
                    logging.info(f"Превью успешно загружено, ID: {photo_id}")
                    response = upload.video(video_file=video_path, group_id=VK_GROUP_ID, name=title,
                                            description=description, cover_id=photo_id)
                    logging.info(f"Видео с превью '{title}' успешно загружено.")

                except Exception as e:
                    logging.error(f"Ошибка загрузки превью '{video_path}': {e}")
                    response = upload.video(video_file=video_path, group_id=VK_GROUP_ID, name=title,
                                           description=description)
                    logging.info(f"Видео без превью '{title}' успешно загружено.")


            else:
                 logging.info(f"Нет превью для видео '{video_path}'.")
                 response = upload.video(video_file=video_path, group_id=VK_GROUP_ID, name=title,
                                         description=description)
                 logging.info(f"Видео без превью '{title}' успешно загружено.")


            video_link = f"https://vk.com/video-{VK_GROUP_ID}_{response['video_id']}"
            logging.info(f"Видео '{title}' успешно загружено: {video_link}")
            return True  # Загрузка успешна

        except Exception as e:
            logging.error(f"Ошибка при загрузке видео '{video_path}', попытка {attempt + 1}: {e}")
            if attempt == max_retries - 1:  # Если это последняя попытка, то не будем пробовать еще раз
                logging.error(f"Загрузка видео '{video_path}' не удалась, сохраняем видео.")
                return False

            time.sleep(retry_delay) # Если не последняя попытка, то ждем, перед новой

    return False



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
            if current_time - publish_time_dt <= timedelta(hours=72):
                return f"https://www.youtube.com/watch?v={video_id}"
            else:
                return None
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении последнего видео: {e}")
        return None


# Функция для скачивания последнего видео с YouTube канала
def download_latest_youtube_video(channel_url):
    file_path_to_delete = None
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

                   if upload_video_to_vk(file_path):
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
       if file_path_to_delete and os.path.exists(file_path_to_delete):
            os.remove(file_path_to_delete)
            logging.info(f"Видео '{file_path_to_delete}' удалено из папки.")


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
                    if upload_video_to_vk(video_path):
                         uploaded_files.add(video_file)
                         os.remove(video_path)
                         logging.info(f"Видео '{video_file}' удалено из папки.")
                    else:
                       logging.error(f"Не удалось загрузить видео '{video_path}'. Видео сохранено.")

            else:
                logging.info("Новых видео не найдено.")
        except Exception as e:
            logging.error(f"Ошибка при обработке папки: {e}")
        time.sleep(60 * 1)  # Задержка 1 минута

# Функция для планирования проверки каналов
def schedule_channels_check():
    threading.Timer(CHECK_INTERVAL, schedule_channels_check).start()  # Запускаем таймер снова
    logging.info("Запланирована проверка каналов...")
    process_channels()

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

# Обработчик сообщений от пользователя
@bot.message_handler(func=lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text)
def download_video(message: Message):
    url = message.text.strip()
    bot.reply_to(message, "Начинаю скачивание видео... Подождите немного.")
    file_path_to_delete = None
    try:
         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
            file_path = ydl.prepare_filename(info)  # Полный путь к скачанному файлу
            file_path_to_delete = file_path

            if os.path.exists(file_path):
                bot.reply_to(message, f"Видео успешно скачано: {file_path}")
                if upload_video_to_vk(file_path):
                    logging.info(f"Видео '{video_title}' успешно загружено в VK.")
                else:
                    logging.error(f"Не удалось загрузить видео '{video_title}' в VK.")

            else:
                bot.reply_to(message, "Ошибка: файл не найден после скачивания.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при скачивании: {e}")
    finally:
        if file_path_to_delete and os.path.exists(file_path_to_delete):
             os.remove(file_path_to_delete)
             logging.info(f"Видео '{file_path_to_delete}' удалено из папки.")


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