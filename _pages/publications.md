---
layout: page
permalink: /publications/
title: publications
description: Auto-updated from Google Scholar.
nav: true
nav_order: 1
---

<div class="publications">

<style>
.theme-toggle { display: flex; gap: 8px; margin-bottom: 1.5rem; flex-wrap: wrap; }
.theme-toggle .btn-theme {
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--global-divider-color);
  background: transparent; color: var(--global-text-color); cursor: pointer;
  font-size: 0.85rem; transition: all 0.2s;
}
.theme-toggle .btn-theme:hover, .theme-toggle .btn-theme.active {
  background: var(--global-theme-color); color: white; border-color: var(--global-theme-color);
}
.pub-section { display: none; }
.pub-section.active { display: block; }
</style>

<div class="theme-toggle">
  <button class="btn-theme active" onclick="showSection('all', this)">All (by year)</button>
  <button class="btn-theme" onclick="showSection('mental-health', this)">Mental Health & NLP</button>
  <button class="btn-theme" onclick="showSection('public-health', this)">Public Health</button>
  <button class="btn-theme" onclick="showSection('cross-cultural', this)">Cross-Cultural AI</button>
  <button class="btn-theme" onclick="showSection('health-interventions', this)">Health Interventions</button>
  <button class="btn-theme" onclick="showSection('other', this)">Other</button>
</div>

<div id="section-all" class="pub-section active">

{% bibliography %}

</div>

<div id="section-mental-health" class="pub-section">

<h2 class="bibliography">Mental Health & NLP</h2>
{% bibliography --query @*[keywords~=mental-health] %}

</div>

<div id="section-public-health" class="pub-section">

<h2 class="bibliography">Public Health</h2>
{% bibliography --query @*[keywords~=public-health] %}

</div>

<div id="section-cross-cultural" class="pub-section">

<h2 class="bibliography">Cross-Cultural AI</h2>
{% bibliography --query @*[keywords~=cross-cultural] %}

</div>

<div id="section-health-interventions" class="pub-section">

<h2 class="bibliography">Health Interventions</h2>
{% bibliography --query @*[keywords~=health-interventions] %}

</div>

<div id="section-other" class="pub-section">

<h2 class="bibliography">Other</h2>
{% bibliography --query @*[keywords~=other] %}

</div>

</div>

<script>
function showSection(id, btn) {
  document.querySelectorAll('.pub-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.btn-theme').forEach(b => b.classList.remove('active'));
  document.getElementById('section-' + id).classList.add('active');
  btn.classList.add('active');
}
</script>
