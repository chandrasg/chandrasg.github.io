---
layout: archive
title: "Lab"
permalink: /group/
author_profile: true
---

{% include base_path %}

## Computational Social Listening Lab

The **[Computational Social Listening Lab](https://csl-lab-upenn.github.io/)** at the University of Pennsylvania develops machine learning and NLP methods to measure health behaviors, disparities, and outcomes across cultures and communities. We use large-scale digital data — social media, electronic health records, online reviews, and smartphone interactions — to uncover insights that improve health outcomes and reduce health disparities.

Visit our **[lab website](https://csl-lab-upenn.github.io/)** for the latest on our research, tools, and projects.

---

### Current Members

<div style="display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin: 20px 0;">
{% for member in site.data.lab-members %}
<div style="text-align: center; width: 140px;">
<img src="{{ member.image }}" alt="{{ member.name }}" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover;">
<br><strong>{{ member.name }}</strong><br><small>{{ member.role }}</small>
</div>
{% endfor %}
</div>

---

### Interested in joining?

We are always looking for motivated students and researchers interested in applications of NLP and machine learning to health — including global mental health, vaccine acceptance, health disparities, and culturally-aware AI. If you are interested, send an email with your CV to sharathg at cis dot upenn dot edu.

See our **[lab website](https://csl-lab-upenn.github.io/)** for more about our alumni and their placements.
