---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

{% include base_path %}

For the most current list, see my <u><a href="https://scholar.google.com/citations?hl=en&user=76_hrfUAAAAJ&view_op=list_works&sortby=pubdate">Google Scholar profile</a></u>.

<em>Publications are auto-updated from Google Scholar.</em>

---

{% assign pubs = site.data.citations | sort: "date" | reverse %}

{% for pub in pubs %}
+ {{ pub.authors | join: ", " }} ({{ pub.date | slice: 0, 4 }}). **{{ pub.title }}**. *{{ pub.publisher }}*. {% if pub.link %}[[Link]]({{ pub.link }}){% endif %}

{% endfor %}
