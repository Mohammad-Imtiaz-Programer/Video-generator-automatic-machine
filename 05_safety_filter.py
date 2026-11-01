"""
Safety Filter Module
---------------------------
Final line of defense against any face the image generator accidentally
produces. Even though 02_prompt_modifier.py instructs the image model to
avoid faces, text-to-image output is never 100% reliable, so every
rendered scene image is re-scanned here before it reaches the final video.

Detection strategy (both passes run on every image; results are merged):
    1. MediaPipe Face Detector (Tasks API) — more accurate, and works well
       on stylised / cartoon faces. Needs the `mediapipe` package plus a
       small .tflite model file, which is downloaded once from Google's
       model store and cached locally in /models.
       (Note: MediaPipe's older `mp.solutions.face_detection` API used in
       early tutorials is deprecated/removed — this uses the current
       Tasks API instead.)
    2. OpenCV Haar Cascade — ships with opencv-python, needs no download,
       and always runs. Used as a guaranteed fallback if MediaPipe is not
       installed, its model can't be downloaded (e.g. no internet on this
       host), or it fails for any other reason.

Every detected face region is:
    - Heavily Gaussian-blurred, AND
    - Covered with a soft, solid near-white ellipse
      (matches the "glowing white light" rule for child characters, and
      simply guarantees no facial features remain visible for anyone).
"""

import os
import urllib.request
import cv2

_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "blaze_face_short_range.tflite")
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def _ensure_mediapipe_model() -> bool:
    """Downloads the MediaPipe face-detector model on first use (a few
    hundred KB). Returns True if the model is present locally, False if it
    could not be obtained — callers must fall back to OpenCV only."""
    if os.path.exists(_MODEL_PATH):
        return True
    try:
        os.makedirs(_MODEL_DIR, exist_ok=True)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        return True
    except Exception:
        return False


class SafetyFilter:
    def __init__(self):
        self._mp = None
        self._mp_detector = None

        try:
            import mediapipe as mp
            if _ensure_mediapipe_model():
                base_options = mp.tasks.BaseOptions(model_asset_path=_MODEL_PATH)
                options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=base_options,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    min_detection_confidence=0.4,
                )
                self._mp_detector = mp.tasks.vision.FaceDetector.create_from_options(options)
                self._mp = mp
        except Exception:
            # mediapipe not installed, model download failed (e.g. no
            # internet), or an unsupported platform -> OpenCV-only mode,
            # which is still fully functional.
            self._mp_detector = None
            self._mp = None

        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )

    def _detect_faces_mediapipe(self, img_bgr):
        boxes = []
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=img_rgb)
        result = self._mp_detector.detect(mp_image)
        for detection in result.detections:
            bbox = detection.bounding_box
            boxes.append((bbox.origin_x, bbox.origin_y, bbox.width, bbox.height))
        return boxes

    def _detect_faces_opencv(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        boxes = list(self._face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(24, 24)))
        boxes += list(self._profile_cascade.detectMultiScale(gray, 1.1, 5, minSize=(24, 24)))
        return boxes

    def enforce_face_safety(self, image_path: str) -> str:
        """Scans the image at `image_path` for any face-like region and
        masks it. Overwrites the file in place and returns the same path."""
        img = cv2.imread(image_path)
        if img is None:
            return image_path

        boxes = []
        if self._mp_detector is not None:
            try:
                boxes = self._detect_faces_mediapipe(img)
            except Exception:
                boxes = []

        # The OpenCV pass always runs too, as a redundant safety net.
        boxes += self._detect_faces_opencv(img)

        for (x, y, bw, bh) in boxes:
            x, y = max(int(x), 0), max(int(y), 0)
            bw, bh = max(int(bw), 1), max(int(bh), 1)
            roi = img[y:y + bh, x:x + bw]
            if roi.size == 0:
                continue
            # Step 1: heavy blur.
            blurred = cv2.GaussianBlur(roi, (99, 99), 30)
            img[y:y + bh, x:x + bw] = blurred
            # Step 2: solid soft-white mask (glowing/concealing effect).
            center = (x + bw // 2, y + bh // 2)
            axes = (max(bw // 2, 1), max(bh // 2, 1))
            cv2.ellipse(img, center, axes, 0, 0, 360, (245, 245, 245), -1)

        cv2.imwrite(image_path, img)
        return image_path
