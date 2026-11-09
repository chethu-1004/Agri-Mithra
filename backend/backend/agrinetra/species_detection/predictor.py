from pathlib import Path
import json

import numpy as np
import tensorflow as tf
import cv2
from PIL import Image, ImageOps


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

# backend/backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = BACKEND_ROOT / "ml_models"

MODEL_PATH = (
    MODEL_DIR /
    "agrinetra_efficientnet_species_final.keras"
)

CLASS_PATH = (
    MODEL_DIR /
    "species_class_names.json"
)


# ---------------------------------------------------------
# SPECIES PREDICTOR
# ---------------------------------------------------------

class SpeciesPredictor:

    def __init__(self):

        self.model = None
        self.class_names = {}
        self.face_cascade = None

        self.image_size = (224, 224)

    # -----------------------------------------------------
    # LOAD MODEL
    # -----------------------------------------------------

    def load(self):

        print("\n========================================")
        print("Loading Agri Mitra Species Model")
        print("========================================")

        print("Model path:")
        print(MODEL_PATH)

        print("Class mapping:")
        print(CLASS_PATH)

        if not MODEL_PATH.exists():

            raise FileNotFoundError(
                f"Species model not found: {MODEL_PATH}"
            )

        if not CLASS_PATH.exists():

            raise FileNotFoundError(
                f"Species class mapping not found: {CLASS_PATH}"
            )

        # Load TensorFlow/Keras model
        self.model = tf.keras.models.load_model(
            MODEL_PATH
        )

        # Load class names
        with open(
            CLASS_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            self.class_names = json.load(file)

        print(
            "[OK] Species model loaded successfully."
        )

        print(
            f"[OK] Number of classes: {len(self.class_names)}"
        )

        print("Classes:")

        for index, name in self.class_names.items():

            print(
                f"   {index}: {name}"
            )

        print("========================================\n")

        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            raise RuntimeError(f"Could not load the OpenCV face detector: {cascade_path}")
        self.face_cascade = cascade

    # -----------------------------------------------------
    # PREDICT
    # -----------------------------------------------------

    def predict(self, image_path):

        if self.model is None:

            self.load()

        # Reject obvious human portraits before running the closed-set plant model.
        image = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        face_image = image.copy()
        face_image.thumbnail((960, 960))
        rgb_array = np.asarray(face_image, dtype=np.uint8)
        gray_array = cv2.equalizeHist(cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY))
        min_face_size = max(36, min(gray_array.shape[:2]) // 12)
        faces = self.face_cascade.detectMultiScale(
            gray_array,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(min_face_size, min_face_size),
        )
        if len(faces):
            return {
                "human_detected": True,
                "analysis_type": "human",
                "species": "",
                "predicted_class": "Human detected",
                "confidence": None,
                "top_predictions": [],
                "model": "OpenCV face detector",
                "recommendation": "A human face was detected. This is not a crop leaf photo. Please upload a clear image of a crop leaf.",
            }

        # Resize
        image = image.resize(
            self.image_size
        )

        # Convert to numpy
        image_array = np.asarray(
            image,
            dtype=np.float32
        )

        # Add batch dimension
        image_array = np.expand_dims(
            image_array,
            axis=0
        )

        # Prediction
        predictions = self.model.predict(
            image_array,
            verbose=0
        )[0]

        # Highest probability
        predicted_index = int(
            np.argmax(predictions)
        )

        confidence = float(
            predictions[predicted_index]
        )

        predicted_class = self.class_names[
            str(predicted_index)
        ]

        # Top 3
        top_indices = np.argsort(
            predictions
        )[::-1][:3]

        top_predictions = []

        for index in top_indices:

            top_predictions.append(
                {
                    "class": self.class_names[
                        str(int(index))
                    ],
                    "confidence": float(
                        predictions[index]
                    )
                }
            )

        return {
            "species": predicted_class,
            "predicted_class": predicted_class,
            "class_index": predicted_index,
            "confidence": confidence,
            "top_predictions": top_predictions
        }


# ---------------------------------------------------------
# GLOBAL PREDICTOR
# ---------------------------------------------------------

predictor = SpeciesPredictor()
