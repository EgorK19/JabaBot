import asyncio
import cv2
import pytesseract
import opennsfw2 as n2
import re
from PIL import Image
from io import BytesIO
from detoxify import Detoxify
from aiogram import Bot
from aiogram.types import File, Sticker
import tempfile
import numpy as np
from typing import Dict
from config import NSFW_THRESHOLD, TOXICITY_THRESHOLD_MEDIA
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
def preprocess_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

def normalize_text(ocr_text: str) -> str:
    ocr_text = ' '.join(ocr_text.split()).lower()
    ocr_text = re.sub('[^a-zа-яё ]', '', ocr_text)
    ocr_text = ' '.join(ocr_text.split())
    return ocr_text

async def process_photo(bot: Bot, text_model: Detoxify, file: File) -> Dict[str, any]:
    buffer = BytesIO()
    await bot.download_file(file.file_path, buffer)
    buffer.seek(0)
    image: Image.Image = Image.open(buffer)
    image_np = np.array(image)
    preprocessed_image = preprocess_image(image_np)
    preprocessed_pil = Image.fromarray(preprocessed_image)
    loop = asyncio.get_event_loop()
    image_for_nsfw = image.resize((224, 224))
    nsfw_probability = await loop.run_in_executor(None, n2.predict_image, image_for_nsfw)
    nsfw_result = {'porn': nsfw_probability}    
    ocr_text: str = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(preprocessed_pil, lang='eng+rus'))
    ocr_text = normalize_text(ocr_text)
    ocr_result = await process_text(text_model, ocr_text)
    if nsfw_result['porn'] > NSFW_THRESHOLD:
        return {'is_violation': True, 'violation_type': 'nsfw_image', 'content': 'NSFW content detected'}
    if ocr_result['toxicity'] > TOXICITY_THRESHOLD_MEDIA:
        return {'is_violation': True, 'violation_type': 'toxic_image_text', 'content': ocr_text}
    return {'is_violation': False}

async def process_video(bot: Bot, text_model: Detoxify, file: File) -> Dict[str, any]:
    loop = asyncio.get_event_loop()
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        await bot.download_file(file.file_path, tmp.name)
        cap = cv2.VideoCapture(tmp.name)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = [int(i * total_frames / 5) for i in range(5)]
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                preprocessed_frame = preprocess_image(frame)
                preprocessed_pil = Image.fromarray(preprocessed_frame)
                ocr_text: str = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(preprocessed_pil, lang='eng+rus'))
                ocr_text = normalize_text(ocr_text)
                ocr_result = await process_text(text_model, ocr_text)
                if ocr_result['toxicity'] > TOXICITY_THRESHOLD_MEDIA:
                    cap.release()
                    return {'is_violation': True, 'violation_type': 'toxic_video_text', 'content': ocr_text}
                image_for_nsfw = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((224, 224))
                nsfw_probability = await loop.run_in_executor(None, n2.predict_image, image_for_nsfw)
                nsfw_result = {'porn': nsfw_probability}
                if nsfw_result['porn'] > NSFW_THRESHOLD:
                    cap.release()
                    return {'is_violation': True, 'violation_type': 'nsfw_video', 'content': 'NSFW content detected'}
        cap.release()
    return {'is_violation': False}

async def process_sticker(bot: Bot, text_model: Detoxify, sticker: Sticker) -> Dict[str, any]:
    loop = asyncio.get_event_loop()
    file_id = sticker.thumb.file_id if sticker.is_animated and sticker.thumb else sticker.file_id
    file = await bot.get_file(file_id)
    buffer = BytesIO()
    await bot.download_file(file.file_path, buffer)
    buffer.seek(0)
    try:
        image: Image.Image = Image.open(buffer)
    except:
        return {'is_violation': False}
    image_np = np.array(image)
    preprocessed_image = preprocess_image(image_np)
    preprocessed_pil = Image.fromarray(preprocessed_image)
    ocr_text: str = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(preprocessed_pil, lang='eng+rus'))
    ocr_text = normalize_text(ocr_text)
    ocr_result = await process_text(text_model, ocr_text)
    if ocr_result['toxicity'] > TOXICITY_THRESHOLD_MEDIA:
        return {'is_violation': True, 'violation_type': 'toxic_sticker_text', 'content': ocr_text}
    image_for_nsfw = image.resize((224, 224))
    nsfw_probability = await loop.run_in_executor(None, n2.predict_image, image_for_nsfw)
    nsfw_result = {'porn': nsfw_probability}
    if nsfw_result['porn'] > NSFW_THRESHOLD:
        return {'is_violation': True, 'violation_type': 'nsfw_sticker', 'content': 'NSFW content detected'}
    return {'is_violation': False}

async def process_text(model: Detoxify, text: str) -> Dict[str, float]:
    if not text.strip():
        return {'toxicity': 0.0}
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, model.predict, text)