import os
import cv2
import numpy as np

FACE_DIR = "known_faces"
TRAINER_DIR = "trainer"
MODEL_PATH = os.path.join(TRAINER_DIR, "trainer.yml")
CONFIDENCE_THRESHOLD = 70

os.makedirs(FACE_DIR, exist_ok=True)
os.makedirs(TRAINER_DIR, exist_ok=True)

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _normalize_lighting(gray_image):
    return cv2.equalizeHist(gray_image)


def detect_face(gray_image):
    gray_eq = _normalize_lighting(gray_image)
    faces = _face_cascade.detectMultiScale(gray_eq, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face = gray_eq[y:y + h, x:x + w]
    return cv2.resize(face, (200, 200))


def save_face_sample(label, image_bgr, sample_index):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    face = detect_face(gray)
    if face is None:
        return False
    label_dir = os.path.join(FACE_DIR, str(label))
    os.makedirs(label_dir, exist_ok=True)
    cv2.imwrite(os.path.join(label_dir, f"{sample_index}.jpg"), face)
    return True


def count_samples(label):
    label_dir = os.path.join(FACE_DIR, str(label))
    if not os.path.isdir(label_dir):
        return 0
    return len([f for f in os.listdir(label_dir) if f.endswith(".jpg")])


def train_model():
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces, labels = [], []
    for label_str in os.listdir(FACE_DIR):
        label_dir = os.path.join(FACE_DIR, label_str)
        if not os.path.isdir(label_dir):
            continue
        try:
            label = int(label_str)
        except ValueError:
            continue
        for filename in os.listdir(label_dir):
            if not filename.endswith(".jpg"):
                continue
            img = cv2.imread(os.path.join(label_dir, filename), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            faces.append(img)
            labels.append(label)
    if not faces:
        return False
    recognizer.train(faces, np.array(labels))
    recognizer.save(MODEL_PATH)
    return True


def model_exists():
    return os.path.isfile(MODEL_PATH)


_recognizer_cache = None
_recognizer_mtime = None


def _get_recognizer():
    global _recognizer_cache, _recognizer_mtime
    mtime = os.path.getmtime(MODEL_PATH)
    if _recognizer_cache is None or mtime != _recognizer_mtime:
        _recognizer_cache = cv2.face.LBPHFaceRecognizer_create()
        _recognizer_cache.read(MODEL_PATH)
        _recognizer_mtime = mtime
    return _recognizer_cache


def recognize_face(image_bgr):
    if not model_exists():
        return None
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    face = detect_face(gray)
    if face is None:
        return None
    recognizer = _get_recognizer()
    label, distance = recognizer.predict(face)
    return {"label": label, "confidence": float(distance)}


def is_match_acceptable(confidence):
    return confidence <= CONFIDENCE_THRESHOLD


def decode_base64_image(base64_string):
    import base64
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]
    img_bytes = base64.b64decode(base64_string)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
