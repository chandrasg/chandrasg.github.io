---
layout: page
permalink: /lab/
redirect_from:
  - /group/
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

<div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 justify-content-center lab-members">
{% for member in site.data.lab-members %}
<div class="col lab-member">
  <img src="{{ member.image }}" alt="{{ member.name }}" class="rounded-circle" loading="lazy">
  <div class="member-name">{{ member.name }}</div>
  <div class="member-role">{{ member.role }}</div>
</div>
{% endfor %}
</div>

---

### Interested in joining?

We are always looking for motivated students and researchers interested in applications of NLP and machine learning to health -- including global mental health, vaccine acceptance, health disparities, and culturally-aware AI. If you are interested, send an email with your CV to sharathg at cis dot upenn dot edu.

See our **[lab website](https://csl-lab-upenn.github.io/)** for more about our alumni and their placements.
