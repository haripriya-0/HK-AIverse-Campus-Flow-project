import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from pypdf import PdfReader


UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True, parents=True)


def normalize_date_value(value):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y', '%d.%m.%y', '%Y/%m/%d', '%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return value


def is_ocr_available():
    return shutil.which('tesseract') is not None


def preprocess_image_for_ocr(image):
    image = image.convert('RGB')
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = image.resize((image.width * 2, image.height * 2))
    image = image.filter(ImageFilter.SHARPEN)
    image = image.point(lambda p: 255 if p > 170 else 0)
    return image


def extract_text_from_image(file_path):
    if not is_ocr_available():
        return ''
    try:
        image = Image.open(file_path)
        processed = preprocess_image_for_ocr(image)
        text = pytesseract.image_to_string(processed, config='--psm 6')
        return text.strip()
    except Exception:
        return ''


def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ''
            pages.append(text)
        return '\n'.join(pages).strip()
    except Exception:
        return ''


def extract_text_from_file(file_path):
    extension = file_path.rsplit('.', 1)[-1].lower()
    if extension in {'png', 'jpg', 'jpeg'}:
        return extract_text_from_image(file_path)
    if extension == 'pdf':
        return extract_text_from_pdf(file_path)
    return ''


def parse_ocr_text(raw_text):
    text = raw_text or ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def clean_value(value):
        value = value.strip().strip(',:;')
        return re.sub(r'\s+', ' ', value)

    def find_value(patterns):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = clean_value(match.group(1))
                if value:
                    return value
        return None

    def find_date_range():
        date_pattern = r'(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})'

        from_match = re.search(r'(?:leave\s*(?:from|starting)|from\s*date|date\s*from)\s*[:\-]?\s*(%s)' % date_pattern, text, re.IGNORECASE)
        to_match = re.search(r'(?:leave\s*to|to\s*date|end\s*date|date\s*to)\s*[:\-]?\s*(%s)' % date_pattern, text, re.IGNORECASE)
        if from_match and to_match:
            return from_match.group(1), to_match.group(1)
        if from_match:
            return from_match.group(1), from_match.group(1)
        if to_match:
            return to_match.group(1), to_match.group(1)

        for pattern in [
            r'(?:leave\s*(?:from|starting)|from\s*date|date\s*from)\s*[:\-]?\s*(?:\()?(%s)(?:\))?\s*(?:to|-)\s*(?:\()?(%s)(?:\))?' % (date_pattern, date_pattern),
            r'(?:leave\s*(?:from|starting)|from\s*date|date\s*from)\s*[:\-]?\s*(%s)' % date_pattern,
            r'(?:leave\s*to|to\s*date|end\s*date|date\s*to)\s*[:\-]?\s*(%s)' % date_pattern,
            r'\bfrom\b\s*(%s)\s*\bto\b\s*(%s)\b' % (date_pattern, date_pattern),
            r'\b(%s)\s*(?:-|to|through|thru)\s*(%s)\b' % (date_pattern, date_pattern),
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return match.group(1), match.group(2)
                return match.group(1), match.group(1)

        for line in lines:
            lower = line.lower()
            if any(keyword in lower for keyword in ['leave from', 'from date', 'date from', 'leave to', 'to date', 'date to', 'from', 'to']):
                dates = re.findall(date_pattern, line)
                if len(dates) >= 2:
                    return dates[0], dates[1]
                if len(dates) == 1:
                    return dates[0], dates[0]

        all_dates = re.findall(date_pattern, text)
        if len(all_dates) >= 2:
            return all_dates[0], all_dates[-1]
        if len(all_dates) == 1:
            return all_dates[0], all_dates[0]
        return None, None

    name = None
    for line in lines:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in ['student name', 'candidate', 'name']) and not any(keyword in lower_line for keyword in ['date', 'organization', 'hospital', 'clinic', 'reason', 'signature']):
            match = re.search(r'(?:student\s+name|candidate|name)\s*[:\-]?\s*([A-Za-z][A-Za-z\s\.]+)', line, re.IGNORECASE)
            if match:
                name = clean_value(match.group(1))
                break

    if not name:
        name = find_value([
            r'name\s*[:\-]?\s*([A-Za-z][A-Za-z\s\.]+)',
            r'student\s*name\s*[:\-]?\s*([A-Za-z][A-Za-z\s\.]+)',
            r'candidate\s*[:\-]?\s*([A-Za-z][A-Za-z\s\.]+)',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b',
        ])

    extracted_date = find_value([
        r'date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})',
        r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b',
        r'\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b',
    ])
    leave_from, leave_to = find_date_range()
    leave_from = normalize_date_value(leave_from or extracted_date)
    leave_to = normalize_date_value(leave_to or extracted_date)

    organization = find_value([
        r'organization\s*[:\-]?\s*([A-Za-z0-9 &./,-]+)',
        r'hospital\s*[:\-]?\s*([A-Za-z0-9 &./,-]+)',
        r'institute\s*[:\-]?\s*([A-Za-z0-9 &./,-]+)',
        r'clinic\s*[:\-]?\s*([A-Za-z0-9 &./,-]+)',
    ])

    if not name and lines:
        for line in lines:
            if len(line.split()) >= 2 and not any(keyword in line.lower() for keyword in ['date', 'hospital', 'organization', 'reason', 'signature']):
                candidate = clean_value(line)
                if candidate and not re.fullmatch(r'\d+', candidate):
                    name = candidate
                    break

    return {
        'name': name,
        'date': extracted_date,
        'leave_from': leave_from,
        'leave_to': leave_to,
        'organization': organization,
        'raw_text': text,
    }
