function analysisScoreText(value){
  if(value===null||value===undefined||value==='')return null;
  const score=Number(value);
  return Number.isFinite(score)&&score>=0&&score<=1?String(Math.round(score*100))+'%':null;
}

function analysisCardsMarkup(analysis){
  if(!analysis||typeof analysis!=='object'||analysis.plant?.status==='human_detected')return '';
  const plant=analysis.plant||{},health=analysis.health||{},disease=analysis.disease||{},recommendation=analysis.recommendation||{};
  const water=analysis.water_status||{},soilMoisture=water.soil_moisture||{};
  const confidence=analysisScoreText(plant.prediction_confidence);
  const healthScore=health.score_percent===null||health.score_percent===undefined?'':Number(health.score_percent);
  const hasHealthScore=Number.isFinite(healthScore)&&healthScore>=0&&healthScore<=100;
  const diseaseConfidence=analysisScoreText(disease.prediction_confidence);
  const alternatives=Array.isArray(plant.top_alternatives)?plant.top_alternatives.filter(item=>item?.name).slice(0,3):[];
  const plantUncertain=plant.status==='uncertain';
  const followUp=[...(Array.isArray(water.next_steps)?water.next_steps:[]),...(Array.isArray(disease.next_steps)?disease.next_steps:[]),...(Array.isArray(recommendation.follow_up)?recommendation.follow_up:[]),...(Array.isArray(recommendation.precautions)?recommendation.precautions:[])];
  const sources=[...(Array.isArray(disease.supporting_sources)?disease.supporting_sources:[]),...(Array.isArray(recommendation.supporting_sources)?recommendation.supporting_sources:[])];
  const symptoms=Array.isArray(disease.visible_symptoms)?disease.visible_symptoms:[];
  const factors=Array.isArray(disease.possible_contributing_factors)?disease.possible_contributing_factors:[];
  const waterValue=water.water_content_percent;
  const hasWaterContent=waterValue!==null&&waterValue!==undefined&&Number.isFinite(Number(waterValue))&&Number(waterValue)>=0&&Number(waterValue)<=100&&water.water_content_metric==='relative_water_content'&&water.measurement_source!=='unavailable';
  const waterPercent=hasWaterContent?Number(waterValue):null;
  const waterMeter=hasWaterContent?`<progress class="analysis-health-meter" max="100" value="${waterPercent}" aria-label="${esc(translateText('Leaf water content'))} ${waterPercent}%"></progress><b class="analysis-health-score">${waterPercent}%</b>`:`<b class="analysis-health-unavailable">${esc(translateText('Unavailable from this image'))}</b>`;
  const moistureLabel=({uncertain:'Uncertain — additional assessment required',adequately_hydrated:'No clear visual signs of water stress',possible_water_stress:'Possible water stress',possible_severe_water_stress:'Possible severe water stress',not_applicable:'Not applicable'})[water.moisture_assessment]||'Uncertain — additional assessment required';
  const stressLabel=({not_assessed:'Not assessed',no_clear_visual_signs:'No clear visual signs of water stress',possible_water_stress:'Possible water stress',possible_severe_water_stress:'Possible severe water stress',uncertain:'Uncertain — additional assessment required',not_applicable:'Not applicable'})[water.visual_water_stress]||'Not assessed';
  const soilValue=soilMoisture.value;
  const hasSoilReading=soilMoisture.status==='measured'&&soilValue!==null&&soilValue!==undefined&&Number.isFinite(Number(soilValue))&&typeof soilMoisture.unit==='string'&&soilMoisture.source!=='unavailable';
  const applicationRate=Number(recommendation.application_rate);
  const hasApplicationRate=Number.isFinite(applicationRate)&&applicationRate>0&&typeof recommendation.application_unit==='string'&&recommendation.application_unit.trim();
  const meter=hasHealthScore?`<progress class="analysis-health-meter" max="100" value="${healthScore}" aria-label="${esc(translateText('Leaf health'))} ${healthScore}%"></progress><b class="analysis-health-score">${healthScore}%</b>`:'<b class="analysis-health-unavailable">'+esc(translateText('Health assessment unavailable'))+'</b>';
  const diseaseUncertain=disease.status==='uncertain';
  const diseaseHeading=disease.name&&!diseaseUncertain?esc(disease.name):esc(translateText(diseaseUncertain?'Uncertain model result':disease.status==='not_configured'?'Disease model unavailable':'No disease prediction was made.'));
  const evidence=String(recommendation.evidence_quality||'insufficient').replaceAll('_',' ');
  const recommendationName=recommendation.fertilizer_name?esc(recommendation.fertilizer_name):esc(translateText('No fertilizer recommendation'));
  return `<section class="analysis-results" aria-label="${esc(translateText('Detailed image analysis'))}">
    <article class="analysis-card"><h3>${esc(translateText('Plant identification'))}</h3><strong>${plantUncertain?esc(translateText('Not confidently identified')):plant.name?esc(plant.name):esc(translateText('Plant not identified'))}</strong>${plantUncertain&&plant.name?`<p>${esc(translateText('Top model candidate'))}: ${esc(plant.name)}</p>`:''}<p>${esc(translateText('Species prediction confidence'))}: ${confidence||esc(translateText('Not provided'))}</p>${confidence?`<small>${esc(translateText('Model score; not a calibrated probability.'))}</small>`:''}${alternatives.length?`<div class="analysis-alternatives"><b>${esc(translateText('Other model classes'))}</b>${alternatives.map(item=>`<span>${esc(item.name)}${analysisScoreText(item.prediction_confidence)?` · ${analysisScoreText(item.prediction_confidence)}`:''}</span>`).join('')}</div>`:''}</article>
    <article class="analysis-card"><h3>${esc(translateText('Leaf health'))}</h3>${meter}<p>${esc(translateText(health.condition==='not_applicable'?'Not applicable to this image':'Health assessment unavailable'))}</p><small>${esc(translateText(health.explanation||'A validated leaf-health model is not available.'))}</small></article>
    <section class="analysis-water-status" aria-label="${esc(translateText('Leaf Water Status'))}"><h3>${esc(translateText('Leaf Water Status'))}</h3><div class="analysis-water-cards">
      <article class="analysis-card"><h4>${esc(translateText('Leaf water content'))}</h4>${waterMeter}<p>${esc(translateText(water.water_content_metric==='relative_water_content'?'Relative water content (RWC)':'Unavailable from this image'))}</p><small>${esc(translateText(water.explanation||'Leaf water content unavailable from this image alone.'))}</small><small>${esc(translateText('Measurement source'))}: ${esc(translateText(water.measurement_source||'unavailable'))}</small>${water.confidence_type==='calibrated_probability'&&water.confidence_percent!==null&&water.confidence_percent!==undefined?`<small>${esc(translateText('Water-status confidence'))}: ${esc(water.confidence_percent)}%</small>`:''}</article>
      <article class="analysis-card"><h4>${esc(translateText('Leaf moisture assessment'))}</h4><strong>${esc(translateText(moistureLabel))}</strong><p>${esc(translateText('No validated leaf water-stress model is available; this image was not assessed for water stress.'))}</p><small>${esc(translateText('Assessment method'))}: ${esc(translateText(water.assessment_method||'unavailable'))}</small></article>
      <article class="analysis-card"><h4>${esc(translateText('Water-stress indicators'))}</h4><strong>${esc(translateText(stressLabel))}</strong>${water.visual_indicators?.length?`<p>${water.visual_indicators.map(item=>esc(translateText(item))).join('; ')}</p>`:`<p>${esc(translateText('No visual indicators were assessed.'))}</p>`}<small>${esc(translateText('Leaf appearance can have several causes; check soil moisture, watering history, and crop conditions before changing irrigation.'))}</small></article>
      <article class="analysis-card"><h4>${esc(translateText('Soil moisture'))}</h4><strong>${hasSoilReading?`${esc(soilValue)} ${esc(soilMoisture.unit)}`:esc(translateText(soilMoisture.status==='not_applicable'?'Not applicable':'Not measured'))}</strong><p>${esc(translateText(soilMoisture.explanation||'An RGB leaf photo cannot measure soil moisture. Check the soil directly or use a calibrated soil sensor.'))}</p><small>${esc(translateText('Measurement source'))}: ${esc(translateText(soilMoisture.source||'unavailable'))}</small></article>
    </div></section>
    <article class="analysis-card"><h3>${esc(translateText('Disease analysis'))}</h3><strong>${diseaseHeading}</strong>${diseaseUncertain&&disease.name?`<p>${esc(translateText('Top model candidate'))}: ${esc(disease.name)}</p>`:''}${disease.name&&diseaseConfidence?`<p>${esc(translateText('Disease prediction confidence'))}: ${diseaseConfidence}</p><small>${esc(translateText('Model score; not a calibrated probability.'))}</small>`:''}<p>${esc(translateText(disease.explanation||''))}</p>${symptoms.length?`<p><b>${esc(translateText('Visible symptoms'))}</b>: ${symptoms.map(item=>esc(translateText(item))).join('; ')}</p>`:''}${factors.length?`<p><b>${esc(translateText('Possible contributing factors'))}</b>: ${factors.map(item=>esc(translateText(item))).join('; ')}</p>`:''}${disease.requires_field_verification&&disease.name?`<small>${esc(translateText('Requires field verification; this is not a confirmed diagnosis.'))}</small>`:''}</article>
    <article class="analysis-card"><h3>${esc(translateText('Fertilizer recommendation'))}</h3><strong>${recommendationName}</strong><span class="tag gray">${esc(translateText('Evidence quality'))}: ${esc(translateText(evidence))}</span>${recommendation.confidence_type==='calibrated_probability'&&recommendation.confidence_percent!==null&&recommendation.confidence_percent!==undefined?`<p>${esc(translateText('Recommendation confidence'))}: ${esc(recommendation.confidence_percent)}%</p>`:''}<p>${esc(translateText(recommendation.reason||''))}</p>${recommendation.target_nutrient?`<p>${esc(translateText('Target nutrient'))}: ${esc(translateText(recommendation.target_nutrient))}</p>`:''}${recommendation.crop_suitability?`<p>${esc(translateText('Crop suitability'))}: ${esc(translateText(recommendation.crop_suitability))}</p>`:''}${recommendation.growth_stage?`<p>${esc(translateText('Growth stage'))}: ${esc(translateText(recommendation.growth_stage))}</p>`:''}${hasApplicationRate?`<p>${esc(translateText('Application rate'))}: ${applicationRate} ${esc(recommendation.application_unit)}</p>`:''}${recommendation.application_method?`<p>${esc(translateText('Application method'))}: ${esc(translateText(recommendation.application_method))}</p>`:''}${recommendation.application_timing?`<p>${esc(translateText('Application timing'))}: ${esc(translateText(recommendation.application_timing))}</p>`:''}${recommendation.concentration_percent!==null&&recommendation.concentration_percent!==undefined?`<p>${esc(translateText('Concentration'))}: ${esc(recommendation.concentration_percent)}%</p>`:''}${sources.length?`<small>${sources.map(source=>esc(source)).join(' · ')}</small>`:''}</article>
    ${followUp.length?`<article class="analysis-card analysis-next-steps"><h3>${esc(translateText('Preventive care and next steps'))}</h3><ul>${followUp.map(item=>`<li>${esc(translateText(item))}</li>`).join('')}</ul></article>`:''}
  </section>`;
}

function analysisSummaryLines(analysis){
  if(!analysis||typeof analysis!=='object')return [];
  const health=analysis.health||{},disease=analysis.disease||{},recommendation=analysis.recommendation||{},water=analysis.water_status||{},soil=water.soil_moisture||{};
  const lines=[];
  lines.push(health.score_percent===null||health.score_percent===undefined?'Leaf health: assessment unavailable':'Leaf health score: '+health.score_percent+'%');
  lines.push(water.water_content_percent===null||water.water_content_percent===undefined?'Leaf water content: unavailable from this image':'Leaf water content: '+water.water_content_percent+'% ('+String(water.water_content_metric||'metric unavailable')+')');
  lines.push('Leaf moisture assessment: '+String(water.moisture_assessment||'uncertain').replaceAll('_',' '));
  lines.push('Visual water stress: '+String(water.visual_water_stress||'not assessed').replaceAll('_',' '));
  lines.push('Soil moisture: '+(soil.status==='measured'&&soil.value!==null&&soil.value!==undefined&&soil.unit?soil.value+' '+soil.unit:'not measured from the image'));
  if(water.confidence_type==='calibrated_probability'&&water.confidence_percent!==null&&water.confidence_percent!==undefined)lines.push('Water-status confidence: '+water.confidence_percent+'% (calibrated)');
  for(const item of water.next_steps||[])lines.push('Water-status next step: '+item);
  lines.push(disease.name?'Possible disease: '+disease.name:(disease.status==='not_configured'?'Disease prediction: model unavailable':'Disease prediction: not assessed'));
  if(disease.prediction_confidence!==null&&disease.prediction_confidence!==undefined)lines.push('Disease model score: '+analysisScoreText(disease.prediction_confidence)+' (not calibrated)');
  lines.push('Fertilizer evidence: '+String(recommendation.evidence_quality||'insufficient').replaceAll('_',' '));
  if(recommendation.reason)lines.push(recommendation.reason);
  if(recommendation.application_rate!==null&&recommendation.application_rate!==undefined&&recommendation.application_unit)lines.push('Application rate: '+recommendation.application_rate+' '+recommendation.application_unit);
  return lines;
}
