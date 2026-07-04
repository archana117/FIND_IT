import os
import re

HAS_EASYOCR = False
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    pass

reader = None

def resolve_image_path(image_path):
    if not image_path:
        return image_path
    if image_path.startswith('http'):
        return image_path
    if os.path.exists(image_path):
        return image_path
    
    # Try resolving relative to FRONTEND_DIR or BASE_DIR
    try:
        from config import Config
        resolved_path = os.path.join(Config.FRONTEND_DIR, image_path)
        if os.path.exists(resolved_path):
            return resolved_path
        resolved_path = os.path.join(Config.BASE_DIR, image_path)
        if os.path.exists(resolved_path):
            return resolved_path
    except Exception:
        pass
        
    return image_path

def get_ocr_reader():
    global reader
    if not HAS_EASYOCR:
        return None
    if reader is None:
        try:
            # Initialize for English language
            # GPU enabled if PyTorch CUDA is available
            reader = easyocr.Reader(['en'], gpu=True)
        except Exception as e:
            try:
                # Retry with gpu=False just in case
                reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e2:
                print(f"Failed to initialize EasyOCR: {e2}")
                return None
    return reader

def extract_text_from_image(image_path):
    """
    Extracts text from the image using EasyOCR.
    Returns the raw extracted text as a single string.
    """
    image_path = resolve_image_path(image_path)
    if not image_path or not os.path.exists(image_path):
        return ""
    
    ocr_reader = get_ocr_reader()
    if not ocr_reader:
        return ""
        
    try:
        results = ocr_reader.readtext(image_path, detail=0)
        return " ".join(results)
    except Exception as e:
        print(f"EasyOCR text extraction failed: {e}")
        return ""

def parse_ocr_details(text):
    """
    Parses extracted OCR text to find specific entities using regular expressions.
    Returns a dictionary of extracted fields.
    """
    details = {
        "name": None,
        "id_number": None,
        "registration_number": None,
        "college_name": None,
        "vehicle_number": None,
        "passport_number": None
    }
    
    if not text:
        return details
        
    text_upper = text.upper()

    # 1. College/University Name
    college_match = re.search(r'([A-Z\s]+(?:COLLEGE|UNIVERSITY|SCHOOL|INSTITUTE|ACADEMY)[A-Z\s]*)', text_upper)
    if college_match:
        details["college_name"] = college_match.group(1).strip()

    # 2. Registration Number
    reg_match = re.search(r'(?:REGISTRATION|REG|REG\s*NO|ROLL\s*NO)\s*[:.-]?\s*([A-Z0-9\-/]+)', text_upper)
    if reg_match:
        details["registration_number"] = reg_match.group(1).strip()
    else:
        # Check for typical roll/reg number patterns
        reg_pattern = re.search(r'\b(20\d{2}[A-Z]{3}\d{4,5}|\b[A-Z0-9]{8,12}\b)\b', text_upper)
        if reg_pattern and not details["id_number"]:
            details["registration_number"] = reg_pattern.group(1).strip()

    # 3. ID Number
    id_match = re.search(r'(?:ID|IDENTITY|CARD|AADHAAR|PAN|LICENCE|LICENSE)\s*(?:NUMBER|NO)?\s*[:.-]?\s*([A-Z0-9\s]{8,16})', text_upper)
    if id_match:
        details["id_number"] = id_match.group(1).strip()
        
    # 4. Vehicle Number (e.g. Indian standard: MH-12-DE-1433 or similar)
    vehicle_match = re.search(r'\b([A-Z]{2}[-\s]?\d{2}[-\s]?[A-Z]{1,2}[-\s]?\d{4})\b', text_upper)
    if vehicle_match:
        details["vehicle_number"] = vehicle_match.group(1).strip()

    # 5. Passport Number (e.g. Letter followed by 7 numbers)
    passport_match = re.search(r'\b([A-Z][0-9]{7,8})\b', text_upper)
    if passport_match:
        details["passport_number"] = passport_match.group(1).strip()

    # 6. Name Extraction (look for Name: [Name])
    name_match = re.search(r'(?:NAME|HOLDER|OWNER)\s*[:.-]?\s*([A-Z\s]{3,25})(?:\n|$|\s{2})', text_upper)
    if name_match:
        # Clean up name: remove common prefix noises
        name_val = name_match.group(1).strip()
        # Ensure it doesn't contain headers
        if not any(x in name_val for x in ["REG", "COLLEGE", "UNIVERSITY", "CARD"]):
            details["name"] = name_val

    return details
