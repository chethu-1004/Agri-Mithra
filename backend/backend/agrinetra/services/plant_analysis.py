"""Response builders for plant analysis that keep model outputs and evidence separate."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConfidenceKind = Literal['uncalibrated_model_score']
EvidenceQuality = Literal['strong', 'moderate', 'limited', 'insufficient', 'not_applicable']
RecommendationConfidenceType = Literal['calibrated_probability']


class PredictionAlternative(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    prediction_confidence: float | None = Field(default=None, ge=0, le=1)


class PlantResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=200)
    prediction_confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_type: ConfidenceKind | None = None
    status: str = Field(max_length=40)
    top_alternatives: list[PredictionAlternative] = Field(default_factory=list, max_length=5)


class HealthResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    score_percent: float | None = Field(default=None, ge=0, le=100)
    condition: Literal['assessment_unavailable', 'not_applicable']
    assessment_confidence: float | None = Field(default=None, ge=0, le=1)
    method: str | None = None
    scope: Literal['single_image'] = 'single_image'
    explanation: str


class SoilMoistureResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: float | None = Field(default=None, ge=0)
    unit: Literal['% VWC', 'm³/m³', 'kPa'] | None = None
    status: Literal['measured', 'not_measured', 'not_applicable']
    source: Literal['sensor', 'verified_record', 'unavailable']
    explanation: str

    @model_validator(mode='after')
    def measurement_has_value_unit_and_source(self):
        if self.value is not None and not isfinite(self.value):
            raise ValueError('Soil-moisture readings must be finite numbers.')
        if self.status == 'measured' and (
            self.value is None or self.unit is None or self.source == 'unavailable'
        ):
            raise ValueError('A soil-moisture measurement requires a value, unit, and real source.')
        if self.status == 'measured' and self.unit == '% VWC' and self.value is not None and self.value > 100:
            raise ValueError('Volumetric soil-moisture percentages must be between 0 and 100.')
        if self.status == 'measured' and self.unit == 'm³/m³' and self.value is not None and self.value > 1:
            raise ValueError('Volumetric soil-moisture ratios must be between 0 and 1.')
        if self.status != 'measured' and self.value is not None:
            raise ValueError('An unmeasured soil-moisture value must be null.')
        if self.status != 'measured' and (self.unit is not None or self.source != 'unavailable'):
            raise ValueError('Unmeasured soil moisture cannot claim a sensor or verified source.')
        return self


class LeafWaterStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    water_content_percent: float | None = Field(default=None, ge=0, le=100)
    water_content_metric: Literal['relative_water_content'] | None = None
    measurement_source: Literal['unavailable', 'laboratory_measurement', 'validated_model', 'specialized_sensor']
    moisture_assessment: Literal[
        'uncertain', 'adequately_hydrated', 'possible_water_stress',
        'possible_severe_water_stress', 'not_applicable',
    ]
    visual_water_stress: Literal[
        'not_assessed', 'no_clear_visual_signs', 'possible_water_stress',
        'possible_severe_water_stress', 'uncertain', 'not_applicable',
    ]
    visual_indicators: list[str] = Field(default_factory=list)
    confidence_percent: float | None = Field(default=None, ge=0, le=100)
    confidence_type: Literal['calibrated_probability'] | None = None
    assessment_method: Literal['unavailable', 'visual_screening', 'validated_model', 'specialized_sensor']
    explanation: str
    next_steps: list[str] = Field(default_factory=list)
    soil_moisture: SoilMoistureResult

    @model_validator(mode='after')
    def water_content_has_a_defined_measurement(self):
        if self.water_content_percent is not None and not isfinite(self.water_content_percent):
            raise ValueError('Water-content percentages must be finite numbers.')
        if self.water_content_percent is None:
            if self.water_content_metric is not None or self.measurement_source != 'unavailable':
                raise ValueError('Unavailable water content must not claim a metric or measurement source.')
        elif self.water_content_metric is None or self.measurement_source == 'unavailable':
            raise ValueError('A water-content percentage requires a defined metric and measurement source.')
        if self.confidence_percent is not None and self.assessment_method != 'validated_model':
            raise ValueError('A water-status confidence percentage requires a validated model.')
        if self.confidence_percent is not None and self.confidence_type != 'calibrated_probability':
            raise ValueError('A water-status confidence percentage must be calibrated.')
        if self.confidence_type is not None and self.confidence_percent is None:
            raise ValueError('A confidence type requires a water-status confidence percentage.')
        if self.assessment_method == 'unavailable' and (
            self.moisture_assessment not in {'uncertain', 'not_applicable'}
            or self.visual_water_stress not in {'not_assessed', 'not_applicable'}
            or self.visual_indicators
        ):
            raise ValueError('Unavailable assessment methods cannot report visual water-stress findings.')
        return self


class DiseaseResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=240)
    prediction_confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_type: ConfidenceKind | None = None
    status: Literal['predicted', 'uncertain', 'not_configured', 'analysis_unavailable', 'not_assessed', 'not_applicable']
    explanation: str
    visible_symptoms: list[str] = Field(default_factory=list)
    possible_contributing_factors: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    requires_field_verification: bool = True
    supporting_sources: list[str] = Field(default_factory=list)


class FertilizerRecommendation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['fertilizer', 'further_assessment', 'not_applicable']
    fertilizer_name: str | None = None
    target_nutrient: str | None = None
    crop_suitability: str | None = None
    growth_stage: str | None = None
    application_rate: float | None = Field(default=None, gt=0)
    application_unit: str | None = None
    application_method: str | None = None
    application_timing: str | None = None
    concentration_percent: float | None = Field(default=None, ge=0, le=100)
    evidence_quality: EvidenceQuality
    confidence_percent: float | None = Field(default=None, ge=0, le=100)
    confidence_type: RecommendationConfidenceType | None = None
    reason: str
    supporting_sources: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)
    precautions: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def rate_requires_units(self):
        if self.application_rate is not None and not self.application_unit:
            raise ValueError('An application rate must include units.')
        if self.application_rate is not None and not self.application_method:
            raise ValueError('An application rate must include its supported application method.')
        if self.concentration_percent is not None and not self.application_method:
            raise ValueError('A concentration must include its supported application method.')
        if self.confidence_percent is not None and self.confidence_type != 'calibrated_probability':
            raise ValueError('A recommendation confidence percentage must be calibrated.')
        if self.confidence_type is not None and self.confidence_percent is None:
            raise ValueError('A confidence type requires a recommendation confidence percentage.')
        if (self.application_rate is not None or self.concentration_percent is not None) and not self.supporting_sources:
            raise ValueError('An application rate or concentration must cite a supporting source.')
        if self.type == 'fertilizer' and (
            not self.fertilizer_name
            or self.evidence_quality not in {'strong', 'moderate'}
            or not self.supporting_sources
        ):
            raise ValueError('A fertilizer recommendation requires a named product and reviewed supporting sources.')
        if self.type == 'further_assessment' and any((
            self.fertilizer_name,
            self.application_rate,
            self.concentration_percent,
        )):
            raise ValueError('Do not present a fertilizer product or rate when further assessment is required.')
        return self


class PlantAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plant: PlantResult
    health: HealthResult
    water_status: LeafWaterStatus
    disease: DiseaseResult
    recommendation: FertilizerRecommendation


HEALTH_UNAVAILABLE = (
    'A validated healthy-versus-unhealthy model or annotated leaf-damage assessment is not available. '
    'The species classifier cannot provide a scientifically supported leaf-health percentage.'
)
FERTILIZER_EVIDENCE_MISSING = (
    'No reviewed crop-, growth-stage-, and soil-specific source is available to support a safe fertilizer '
    'choice or application rate.'
)
WATER_STATUS_UNAVAILABLE = (
    'Leaf water content unavailable from this image alone. '
    'Leaf appearance can have several causes; check soil moisture, watering history, and crop conditions before changing irrigation.'
)
SOIL_MOISTURE_UNAVAILABLE = (
    'Soil moisture is not measured by a leaf photograph. No soil-moisture sensor reading or verified record is connected.'
)
WATER_STATUS_NEXT_STEPS = [
    'Check soil moisture directly or use a calibrated soil sensor; a leaf photograph cannot measure soil moisture.',
    'Before changing irrigation, consider crop stage, recent irrigation and rainfall, and other possible causes of wilting.',
]


def _water_status_result(*, human_detected: bool) -> dict:
    if human_detected:
        return {
            'water_content_percent': None,
            'water_content_metric': None,
            'measurement_source': 'unavailable',
            'moisture_assessment': 'not_applicable',
            'visual_water_stress': 'not_applicable',
            'visual_indicators': [],
            'confidence_percent': None,
            'assessment_method': 'unavailable',
            'explanation': 'This is not a crop leaf image.',
            'next_steps': [],
            'soil_moisture': {
                'value': None,
                'unit': None,
                'status': 'not_applicable',
                'source': 'unavailable',
                'explanation': SOIL_MOISTURE_UNAVAILABLE,
            },
        }
    return {
        'water_content_percent': None,
        'water_content_metric': None,
        'measurement_source': 'unavailable',
        'moisture_assessment': 'uncertain',
        'visual_water_stress': 'not_assessed',
        'visual_indicators': [],
        'confidence_percent': None,
        'assessment_method': 'unavailable',
        'explanation': WATER_STATUS_UNAVAILABLE,
        'next_steps': WATER_STATUS_NEXT_STEPS,
        'soil_moisture': {
            'value': None,
            'unit': None,
            'status': 'not_measured',
            'source': 'unavailable',
            'explanation': SOIL_MOISTURE_UNAVAILABLE,
        },
    }


def _valid_confidence(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if isfinite(score) and 0 <= score <= 1 else None


def _name(value) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    return label[:240] or None


def _alternatives(values) -> list[dict]:
    if not isinstance(values, (list, tuple)):
        return []
    output = []
    for item in values[:5]:
        if not isinstance(item, dict):
            continue
        label = _name(item.get('class') or item.get('label') or item.get('species'))
        if not label:
            continue
        output.append({
            'name': label[:200],
            'prediction_confidence': _valid_confidence(item.get('confidence')),
        })
    return output


def _health_result(*, human_detected: bool) -> dict:
    return {
        'score_percent': None,
        'condition': 'not_applicable' if human_detected else 'assessment_unavailable',
        'assessment_confidence': None,
        'method': None,
        'scope': 'single_image',
        'explanation': 'This is not a crop leaf image.' if human_detected else HEALTH_UNAVAILABLE,
    }


def _fertilizer_result(*, human_detected: bool) -> dict:
    if human_detected:
        return {
            'type': 'not_applicable',
            'evidence_quality': 'not_applicable',
            'confidence_percent': None,
            'reason': 'A crop leaf was not analyzed.',
        }
    return {
        'type': 'further_assessment',
        'fertilizer_name': None,
        'target_nutrient': None,
        'growth_stage': None,
        'application_rate': None,
        'application_unit': None,
        'concentration_percent': None,
        'evidence_quality': 'insufficient',
        'confidence_percent': None,
        'reason': FERTILIZER_EVIDENCE_MISSING,
        'supporting_sources': [],
        'follow_up': [
            'Check the crop growth stage and inspect more than one leaf.',
            'Use a soil test and local agricultural extension guidance before selecting a fertilizer or rate.',
        ],
        'precautions': ['Do not apply fertilizer or pesticide solely from this image classification.'],
    }


def build_species_analysis(
    species_result: dict,
    *,
    disease_result: dict | None = None,
    disease_status: str = 'not_configured',
    prediction_status: str = 'predicted',
) -> dict:
    """Build an additive API object; the old species response fields remain unchanged."""
    species_result = species_result if isinstance(species_result, dict) else {}
    human_detected = species_result.get('human_detected') is True or species_result.get('analysis_type') == 'human'
    species_name = None if human_detected else _name(
        species_result.get('species') or species_result.get('predicted_class')
    )
    confidence = None if human_detected else _valid_confidence(species_result.get('confidence'))

    if human_detected:
        plant_status = 'human_detected'
        disease = {
            'name': None,
            'prediction_confidence': None,
            'confidence_type': None,
            'status': 'not_applicable',
            'explanation': 'A human face was detected; disease analysis was not run.',
            'requires_field_verification': False,
        }
    else:
        plant_status = 'uncertain' if prediction_status == 'UNCERTAIN' else 'predicted'
        if disease_result:
            disease_confidence = _valid_confidence(disease_result.get('confidence'))
            disease = {
                'name': _name(disease_result.get('name')),
                'prediction_confidence': disease_confidence,
                'confidence_type': 'uncalibrated_model_score' if disease_confidence is not None else None,
                'status': 'uncertain' if disease_result.get('status') == 'UNCERTAIN' else 'predicted',
                'explanation': 'This is a model prediction, not a confirmed diagnosis. Verify symptoms in the field.',
            }
        else:
            known_status = disease_status if disease_status in {'not_configured', 'analysis_unavailable'} else 'not_assessed'
            explanation = (
                'The disease model is not installed or has no usable class mapping.'
                if known_status == 'not_configured'
                else 'No disease prediction was made for this photo.'
            )
            disease = {
                'name': None,
                'prediction_confidence': None,
                'confidence_type': None,
                'status': known_status,
                'explanation': explanation,
            }

    analysis = {
        'plant': {
            'name': species_name,
            'prediction_confidence': confidence,
            'confidence_type': 'uncalibrated_model_score' if confidence is not None and not human_detected else None,
            'status': plant_status,
            'top_alternatives': [] if human_detected else _alternatives(species_result.get('top_predictions')),
        },
        'health': _health_result(human_detected=human_detected),
        'water_status': _water_status_result(human_detected=human_detected),
        'disease': disease,
        'recommendation': _fertilizer_result(human_detected=human_detected),
    }
    return PlantAnalysis.model_validate(analysis).model_dump()


def build_disease_analysis(label: str, confidence, *, status: str) -> dict:
    """Describe the legacy disease-classifier output without converting it to a health score."""
    disease_label = _name(label)
    crop_name = None
    if disease_label and '___' in disease_label:
        crop_name, disease_label = disease_label.split('___', 1)
    score = _valid_confidence(confidence)
    disease_status = 'uncertain' if status == 'UNCERTAIN' else 'predicted'
    analysis = {
        'plant': {
            'name': _name(crop_name),
            'prediction_confidence': None,
            'confidence_type': None,
            'status': 'crop_from_disease_class' if crop_name else 'not_assessed',
            'top_alternatives': [],
        },
        'health': _health_result(human_detected=False),
        'water_status': _water_status_result(human_detected=False),
        'disease': {
            'name': disease_label,
            'prediction_confidence': score,
            'confidence_type': 'uncalibrated_model_score' if score is not None else None,
            'status': disease_status,
            'explanation': 'This is a model prediction, not a confirmed diagnosis. Verify symptoms in the field.',
        },
        'recommendation': _fertilizer_result(human_detected=False),
    }
    return PlantAnalysis.model_validate(analysis).model_dump()
