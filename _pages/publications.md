---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

{% include base_path %}

<em>Publications are auto-updated from Google Scholar.</em>

---

{% assign pubs = site.data.citations | sort: "date" | reverse %}

{% for pub in pubs %}
+ {{ pub.authors | join: ", " }} ({{ pub.date | slice: 0, 4 }}). **{{ pub.title }}**. *{{ pub.publisher }}*. {% if pub.link %}[[Link]]({{ pub.link }}){% endif %}

{% endfor %}
