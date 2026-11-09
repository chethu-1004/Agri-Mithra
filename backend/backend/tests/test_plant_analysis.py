import pytest
from pydantic import ValidationError

from agrinetra.services.plant_analysis import (
    build_disease_analysis,
    build_species_analysis,
    FertilizerRecommendation,
    LeafWaterStatus,
    SoilMoistureResult,
)


def test_species_analysis_keeps_model_score_separate_from_unavailable_health():
    result = build_species_analysis({
        'species': 'Pongamia Pinnata (P7)',
        'confidence': 0.72,
        'top_predictions': [
            {'class': 'Pongamia Pinnata (P7)', 'confidence': 0.72},
            {'class': 'Arjun (P1)', 'confidence': 0.18},
        ],
    }, disease_status='not_configured')

    assert result['plant']['name'] == 'Pongamia Pinnata (P7)'
    assert result['plant']['prediction_confidence'] == pytest.approx(0.72)
    assert result['plant']['confidence_type'] == 'uncalibrated_model_score'
    assert result['plant']['top_alternatives'][1]['name'] == 'Arjun (P1)'
    assert result['health']['score_percent'] is None
    assert result['health']['assessment_confidence'] is None
    assert result['health']['condition'] == 'assessment_unavailable'
    assert result['disease']['name'] is None
    assert result['disease']['status'] == 'not_configured'
    recommendation = result['recommendation']
    assert recommendation['type'] == 'further_assessment'
    assert recommendation['evidence_quality'] == 'insufficient'
    assert recommendation['confidence_percent'] is None
    assert recommendation['application_rate'] is None
    assert recommendation['concentration_percent'] is None
    assert recommendation['fertilizer_name'] is None


def test_human_image_is_not_reported_as_a_plant_or_fertilizer_case():
    result = build_species_analysis({
        'human_detected': True,
        'analysis_type': 'human',
        'predicted_class': 'Human detected',
        'confidence': None,
    })

    assert result['plant']['name'] is None
    assert result['plant']['prediction_confidence'] is None
    assert result['plant']['status'] == 'human_detected'
    assert result['health']['condition'] == 'not_applicable'
    assert result['recommendation']['type'] == 'not_applicable'
    assert result['recommendation']['application_rate'] is None
    assert result['water_status']['moisture_assessment'] == 'not_applicable'
    assert result['water_status']['water_content_percent'] is None


def test_species_analysis_does_not_infer_leaf_or_soil_moisture_from_rgb():
    result = build_species_analysis({
        'species': 'Pongamia Pinnata (P7)',
        'confidence': 0.73,
    })

    water = result['water_status']
    assert water['water_content_percent'] is None
    assert water['water_content_metric'] is None
    assert water['measurement_source'] == 'unavailable'
    assert water['confidence_percent'] is None
    assert water['moisture_assessment'] == 'uncertain'
    assert water['visual_water_stress'] == 'not_assessed'
    assert water['visual_indicators'] == []
    assert water['soil_moisture']['value'] is None
    assert water['soil_moisture']['status'] == 'not_measured'
    assert water['soil_moisture']['source'] == 'unavailable'
    assert water['next_steps']


def test_water_content_requires_defined_relative_water_content_measurement():
    with pytest.raises(ValidationError):
        LeafWaterStatus(
            water_content_percent=73,
            water_content_metric=None,
            measurement_source='validated_model',
            moisture_assessment='uncertain',
            visual_water_stress='not_assessed',
            assessment_method='unavailable',
            explanation='Invalid fixture.',
            soil_moisture={
                'value': None,
                'unit': None,
                'status': 'not_measured',
                'source': 'unavailable',
                'explanation': 'No measurement.',
            },
        )


def test_soil_moisture_rejects_invalid_sensor_units_and_unmeasured_values():
    with pytest.raises(ValidationError):
        SoilMoistureResult(
            value=1.2,
            unit='m³/m³',
            status='measured',
            source='sensor',
            explanation='Invalid ratio.',
        )
    with pytest.raises(ValidationError):
        SoilMoistureResult(
            value=25,
            unit='% VWC',
            status='not_measured',
            source='unavailable',
            explanation='Contradictory fixture.',
        )


def test_invalid_model_confidences_are_not_returned_as_scores():
    result = build_species_analysis({
        'species': 'Tomato',
        'confidence': 1.4,
        'top_predictions': [{'class': 'Tomato', 'confidence': float('nan')}],
    })

    assert result['plant']['prediction_confidence'] is None
    assert result['plant']['confidence_type'] is None
    assert result['plant']['top_alternatives'][0]['prediction_confidence'] is None


def test_disease_analysis_does_not_turn_disease_score_into_health_score():
    result = build_disease_analysis('Tomato___Early_blight', 0.88, status='SUCCESS')

    assert result['plant']['name'] == 'Tomato'
    assert result['plant']['prediction_confidence'] is None
    assert result['disease']['name'] == 'Early_blight'
    assert result['disease']['prediction_confidence'] == pytest.approx(0.88)
    assert result['health']['score_percent'] is None
    assert result['recommendation']['evidence_quality'] == 'insufficient'


def test_recommendation_rejects_rates_without_units():
    with pytest.raises(ValidationError):
        FertilizerRecommendation(
            type='fertilizer',
            evidence_quality='strong',
            reason='Test fixture.',
            application_rate=20,
        )


def test_recommendation_rejects_rate_without_source_or_method():
    with pytest.raises(ValidationError):
        FertilizerRecommendation(
            type='fertilizer',
            fertilizer_name='Example product',
            evidence_quality='strong',
            reason='Test fixture.',
            application_rate=20,
            application_unit='kg/ha',
            application_method='soil application',
        )


def test_recommendation_rejects_rate_without_application_method():
    with pytest.raises(ValidationError):
        FertilizerRecommendation(
            type='fertilizer',
            fertilizer_name='Example product',
            evidence_quality='strong',
            reason='Test fixture.',
            application_rate=20,
            application_unit='kg/ha',
            supporting_sources=['Reviewed source'],
        )


def test_recommendation_rejects_uncalibrated_confidence_percent():
    with pytest.raises(ValidationError):
        FertilizerRecommendation(
            type='further_assessment',
            evidence_quality='insufficient',
            reason='Test fixture.',
            confidence_percent=70,
        )
