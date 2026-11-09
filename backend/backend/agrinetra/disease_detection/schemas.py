from pydantic import BaseModel,Field
class RecommendationOut(BaseModel):
    symptoms:list[str]=Field(default_factory=list)
    prevention:list[str]=Field(default_factory=list)
    treatment:list[str]=Field(default_factory=list)
class PredictionOut(BaseModel):
    disease:str
    predicted_class:str
    confidence:float=Field(ge=0,le=1)
class DiseasePredictionResponse(BaseModel):
    status:str
    scan_id:str
    prediction:PredictionOut|None=None
    recommendation:RecommendationOut|None=None
    message:str|None=None
