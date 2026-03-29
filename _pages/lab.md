---
layout: page
permalink: /lab/
title: lab
description: The Computational Social Listening Lab at the University of Pennsylvania.
nav: true
nav_order: 4
---

## Computational Social Listening Lab

The **[Computational Social Listening Lab](https://csl-lab-upenn.github.io/)** develops machine learning and NLP methods to measure health behaviors, disparities, and outcomes across cultures and communities. We use large-scale digital data -- social media, electronic health records, online reviews, and smartphone interactions -- to uncover insights that improve health outcomes and reduce health disparities.

Visit our **[lab website](https://csl-lab-upenn.github.io/)** for the latest on our research, tools, and projects.

---

### Current Members

<div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 justify-content-center" style="margin: 1.5rem 0;">
{% for member in site.data.lab-members %}
<div class="col text-center mb-4">
  <img src="{{ member.image }}" alt="{{ member.name }}" class="rounded-circle" loading="lazy" style="width: 110px; height: 110px; object-fit: cover; border: 3px solid var(--global-divider-color);">
  <div class="mt-2"><strong style="font-size: 0.9rem;">{{ member.name }}</strong></div>
  <div style="font-size: 0.8rem; color: var(--global-text-color-light);">{{ member.role }}</div>
</div>
{% endfor %}
</div>

---

### Interested in joining?

We are always looking for motivated students and researchers interested in applications of NLP and machine learning to health -- including global mental health, vaccine acceptance, health disparities, and culturally-aware AI. If you are interested, send an email with your CV to sharathg at cis dot upenn dot edu.

See our **[lab website](https://csl-lab-upenn.github.io/)** for more about our alumni and their placements.
