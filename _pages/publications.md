---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

{% include base_path %}

<em>Auto-updated from Google Scholar.</em>

---

{% assign pubs = site.data.citations | sort: "date" | reverse %}

<ul class="pub-list">
{% for pub in pubs %}
<li>{{ pub.authors | join: ", " }} ({{ pub.date | slice: 0, 4 }}). <strong>{{ pub.title }}</strong>. <em>{{ pub.publisher }}</em>.{% if pub.link %} <a href="{{ pub.link }}">[Link]</a>{% endif %}</li>
{% endfor %}
</ul>
