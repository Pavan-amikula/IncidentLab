// Contextual help for the retained advanced research and native archive pages.
const help = {
  model:'Choose the saved checkpoint used to score archived telemetry. This selection does not train a model.',
  case:'Select a held-out RCAEval case. These observations were collected previously; this is historical replay.',
  load:'Load saved telemetry and CPU predictions for the selected case or trial. This does not start live requests.',
  next:'Show the next archived minute and its scored candidate services.',
  play:'Advance saved observations once per second, or pause replay. The timestamps remain historical.',
  trial:'Choose a saved native HTTP trial to inspect measurements and trace evidence.',
  'observer-stream':'Choose a durable raw-event stream. Its timestamp tells you whether observations are recent or archived.',
  'diagnosis-policy':'Saved LLM comparison policy. New generation is disabled in the laptop profile.',
  diagnose:'Disabled on this laptop. Saved explanations can contain unsupported statements; review citations yourself.'
};
for(const element of document.querySelectorAll('button,select,summary,a')) {
  element.title = help[element.id] || (element.tagName==='SUMMARY'?'Expand saved technical details. No experiment is launched.':'Open the linked view for more detail.');
  if(!element.getAttribute('aria-label')&&element.tagName==='BUTTON')element.setAttribute('aria-label',element.textContent.trim()+'. '+element.title);
}
const guide=document.createElement('section');
guide.innerHTML='<h2>Advanced archive view</h2><p>This page contains saved research or native experiment results. Use <a href="/">your workspace</a> for a guided introduction, a fresh one-minute live demo, Kubernetes results and downloadable graphs. Hover over controls for their purpose.</p><p>For research replay: choose a case → load telemetry → step through minutes. Read the score against its threshold, then inspect candidate services and feature changes. A ranking is an investigation hypothesis.</p>';
document.querySelector('main').prepend(guide);
// A changed selection should update its displayed data, not retain the old trial.
for(const id of ['model','case','trial']) {
  document.getElementById(id)?.addEventListener('change',()=>document.getElementById('load')?.click());
}
if(document.getElementById('diagnose')) {
  document.getElementById('diagnose').hidden=true;
  document.getElementById('diagnosis-policy').disabled=true;
  const p=document.createElement('p');p.textContent='New LLM generation is disabled on this laptop. Saved explanations remain available for research review; unsupported claims were observed.';
  document.getElementById('diagnosis').before(p);
}
