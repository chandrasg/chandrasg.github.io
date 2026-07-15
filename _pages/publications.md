---
layout: page
permalink: /publications/
title: publications
description: Auto-updated from Google Scholar. Classified into research themes automatically.
nav: true
nav_order: 1
---

<div class="pub-filters" role="group" aria-label="Filter publications by research theme">
  <button class="active" aria-pressed="true" onclick="showPubs('all', this)">All</button>
  <button aria-pressed="false" onclick="showPubs('mental-health', this)">Mental Health & NLP</button>
  <button aria-pressed="false" onclick="showPubs('public-health', this)">Public Health</button>
  <button aria-pressed="false" onclick="showPubs('cross-cultural', this)">Cross-Cultural AI</button>
  <button aria-pressed="false" onclick="showPubs('health-interventions', this)">Health Interventions</button>
  <button aria-pressed="false" onclick="showPubs('personality-and-social-media', this)">Personality & Social Media</button>
  <button aria-pressed="false" onclick="showPubs('multimedia-and-images', this)">Multimedia & Images</button>
  <button aria-pressed="false" onclick="showPubs('nlp-and-machine-learning', this)">NLP & ML</button>
  <button aria-pressed="false" onclick="showPubs('other', this)">Other</button>
</div>

<div id="pub-all" class="pub-section publications active">

{% bibliography %}

</div>

<div id="pub-mental-health" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/mental-health.jpg" alt="Mental Health & NLP">
  <div class="theme-info">
    <h2>Mental Health & NLP</h2>
    <p>Detecting and measuring depression, loneliness, ADHD, stress, and well-being from language and images on social media. Building equitable models across racial and cultural groups.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=mental-health] %}

</div>

<div id="pub-public-health" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/public-health.jpg" alt="Public Health">
  <div class="theme-info">
    <h2>Public Health</h2>
    <p>Social media and digital data for public health surveillance – COVID-19, vaccines, substance use, cardiovascular risk, and health behaviors at population scale.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=public-health] %}

</div>

<div id="pub-cross-cultural" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/cross-cultural.png" alt="Cross-Cultural AI">
  <div class="theme-info">
    <h2>Cross-Cultural AI</h2>
    <p>How language, emotion, and social behavior vary across cultures and communities – emoji usage, politeness norms, gender, racial equity in AI.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=cross-cultural] %}

</div>

<div id="pub-health-interventions" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/health-interventions.jpg" alt="Health Interventions">
  <div class="theme-info">
    <h2>Conversational AI for Health Interventions</h2>
    <p>Culturally aware conversational agents and digital health interventions for behavior change, integrating patient-generated data into clinical care.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=health-interventions] %}

</div>

<div id="pub-personality-and-social-media" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/personality.png" alt="Personality & Social Media">
  <div class="theme-info">
    <h2>Personality & Social Media</h2>
    <p>Understanding personality traits and self-presentation through social media content – posted images, language patterns, and user behavior on Twitter, Facebook, and Flickr.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=personality-and-social-media] %}

</div>

<div id="pub-multimedia-and-images" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/multimedia.jpg" alt="Multimedia & Images">
  <div class="theme-info">
    <h2>Multimedia & Images</h2>
    <p>Perceptual image/video quality, 3D synthesized view quality, audio quality, and computer vision for medical imaging and content analysis.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=multimedia-and-images] %}

</div>

<div id="pub-nlp-and-machine-learning" class="pub-section publications">
<div class="theme-header">
  <img src="/assets/img/themes/nlp-ml.jpg" alt="NLP & Machine Learning">
  <div class="theme-info">
    <h2>NLP & Machine Learning</h2>
    <p>Methods in natural language processing, topic modeling, LLMs, and machine learning — including language markers, cultural lexica, and benchmark evaluation.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=nlp-and-machine-learning] %}

</div>

<div id="pub-other" class="pub-section publications">
<div class="theme-header">
  <div class="theme-info">
    <h2>Other</h2>
    <p>Additional publications spanning reviews, commentaries, and interdisciplinary collaborations.</p>
  </div>
</div>

{% bibliography --query @*[keywords~=other] %}

</div>

<script>
function showPubs(id, btn) {
  document.querySelectorAll('.pub-section').forEach(function(s) { s.classList.remove('active'); });
  document.querySelectorAll('.pub-filters button').forEach(function(b) {
    b.classList.remove('active');
    b.setAttribute('aria-pressed', 'false');
  });
  document.getElementById('pub-' + id).classList.add('active');
  btn.classList.add('active');
  btn.setAttribute('aria-pressed', 'true');
  window.scrollTo({ top: document.querySelector('.pub-filters').offsetTop - 80, behavior: 'smooth' });
}
</script>
