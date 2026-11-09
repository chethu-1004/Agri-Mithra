from agrinetra.database.models import TreatmentRecommendation
DEFAULT={'symptoms':['Leaf spots, yellowing, or tissue damage may occur. Confirm the diagnosis with a local agricultural expert.'],'prevention':['Use clean planting material.','Monitor crops regularly and remove heavily affected plant material safely.'],'treatment':['Follow locally approved agricultural guidance and product labels. Avoid applying pesticides without confirming the diagnosis.']}
def get_recommendation(db,disease_key):
    row=db.query(TreatmentRecommendation).filter(TreatmentRecommendation.disease_key==disease_key).first()
    if row: return {'symptoms':row.symptoms,'prevention':row.prevention,'treatment':row.treatment}
    return DEFAULT
