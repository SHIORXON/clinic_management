"""
Yuz verifikatsiyasi moduli.

Haqiqiy solishtirish `face_recognition` (dlib) kutubxonasi bilan bajariladi. U o'rnatilmagan,
`FACE_VERIFICATION_ENABLED=False` yoki `FACE_ENCRYPTION_KEY` bo'sh bo'lsa, `is_available()` False
qaytaradi va tizim yuz tekshiruvini O'TKAZILGAN deb hisoblamaydi.

Rasm hech qayerda saqlanmaydi: faqat 128 o'lchamli vektor Fernet bilan shifrlanib bazaga yoziladi.

Cheklov: bu modul "jonlilik" (liveness) tekshiruvini QILMAYDI, ya'ni xodim rasmini ekrandan
ko'rsatib aldash ehtimoli mavjud. Jiddiy himoya uchun alohida liveness xizmati kerak.
"""
import io

from django.conf import settings

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_SIDE_PX = 1280


class FaceError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


def _lib():
    try:
        import face_recognition  # noqa: WPS433

        return face_recognition
    except ImportError:
        return None


def runtime_status():
    return {
        "enabled_in_settings": bool(settings.FACE_VERIFICATION_ENABLED),
        "library_installed": _lib() is not None,
        "key_configured": bool(settings.FACE_ENCRYPTION_KEY),
        "available": is_available(),
    }


def is_available():
    return bool(settings.FACE_VERIFICATION_ENABLED and settings.FACE_ENCRYPTION_KEY and _lib() is not None)


def _fernet():
    from cryptography.fernet import Fernet

    if not settings.FACE_ENCRYPTION_KEY:
        raise FaceError("FACE_ENCRYPTION_KEY .env faylida sozlanmagan.")
    try:
        return Fernet(settings.FACE_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise FaceError("FACE_ENCRYPTION_KEY noto'g'ri formatda.") from exc


def encrypt_embedding(vector):
    import numpy as np

    return _fernet().encrypt(np.asarray(vector, dtype="float64").tobytes())


def decrypt_embedding(blob):
    import numpy as np
    from cryptography.fernet import InvalidToken

    try:
        raw = _fernet().decrypt(bytes(blob))
    except InvalidToken as exc:
        raise FaceError("Yuz ma'lumotini ochib bo'lmadi (shifrlash kaliti o'zgargan bo'lishi mumkin).") from exc
    return np.frombuffer(raw, dtype="float64")


def distance(a, b):
    import numpy as np

    return float(np.linalg.norm(np.asarray(a, dtype="float64") - np.asarray(b, dtype="float64")))


def embedding_from_image(image_file):
    """Yuklangan rasmdan bitta yuzning vektorini oladi. Rasm diskka yozilmaydi."""
    import numpy as np
    from PIL import Image, UnidentifiedImageError

    lib = _lib()
    if lib is None:
        raise FaceError("Yuz kutubxonasi o'rnatilmagan.")

    image_file.seek(0)
    data = image_file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise FaceError("Rasm hajmi juda katta (maksimum 3 MB).")
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise FaceError("Rasm formati noto'g'ri.") from exc
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    arr = np.array(img)

    locations = lib.face_locations(arr)
    if len(locations) == 0:
        raise FaceError("Rasmda yuz topilmadi. Yaxshi yoritilgan joyda, yuzingizni to'liq ko'rsating.")
    if len(locations) > 1:
        # Orqa fondagi kichik/soxta aniqlashlar xalaqit bermasin: asosiy yuz boshqalardan kamida 2 baravar
        # katta bo'lsa, o'sha olinadi; aks holda kadrda bir nechta odam bor deb rad etiladi.
        def area(loc):
            top, right, bottom, left = loc
            return max(0, bottom - top) * max(0, right - left)

        ranked = sorted(locations, key=area, reverse=True)
        if area(ranked[0]) < 2 * area(ranked[1]):
            raise FaceError("Rasmda bir nechta yuz bor. Kadrda faqat siz bo'lishingiz kerak.")
        locations = [ranked[0]]
    encodings = lib.face_encodings(arr, known_face_locations=locations)
    if not encodings:
        raise FaceError("Yuzdan ma'lumot olib bo'lmadi. Qayta urinib ko'ring.")
    return encodings[0]
