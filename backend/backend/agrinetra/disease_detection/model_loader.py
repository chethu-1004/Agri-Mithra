import json
from pathlib import Path
from agrinetra.config import settings
from agrinetra.disease_detection.preprocessing import prepare_image
class ModelUnavailable(RuntimeError): pass
class Predictor:
    def __init__(self): self.model=None; self.labels=[]; self.metadata={}; self.error='Model has not been loaded.'
    def load(self):
        p=Path(settings.model_path)
        if not p.is_absolute(): p=Path(__file__).resolve().parents[2]/p
        lp=Path(settings.class_labels_path)
        if not lp.is_absolute(): lp=Path(__file__).resolve().parents[2]/lp
        mp=Path(settings.model_metadata_path)
        if not mp.is_absolute(): mp=Path(__file__).resolve().parents[2]/mp
        if not p.exists(): self.error=f'Model file not found: {p}'; return
        try:
            import tensorflow as tf
            self.model=tf.keras.models.load_model(p)
            self.labels=json.loads(lp.read_text(encoding='utf-8-sig'))
            if isinstance(self.labels,dict): self.labels=self.labels.get('classes',[])
            self.metadata=json.loads(mp.read_text(encoding='utf-8-sig')) if mp.exists() else {}
            self.error=''
        except Exception as exc: self.error=f'Model load failed: {exc}'
    def predict(self,path):
        if self.model is None: raise ModelUnavailable(self.error or 'Trained model is unavailable.')
        from tensorflow.keras.applications.efficientnet import preprocess_input
        batch=prepare_image(path)
        probabilities=self.model.predict(preprocess_input(batch),verbose=0)[0]
        import numpy as np
        idx=int(np.argmax(probabilities)); label=self.labels[idx] if idx<len(self.labels) else f'class_{idx}'
        return label,float(probabilities[idx])
predictor=Predictor()
