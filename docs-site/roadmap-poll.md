---
title: "Community Poll — What should Drift focus on?"
description: "Anonymous poll to help shape the Drift roadmap. 30 seconds, no account required."
---

# What should Drift focus on?

Drift is evolving. To set the right priorities, we'd like to know what matters most to you.

**Anonymous. 30 seconds. No account required.**
Results inform the roadmap — not a commitment to specific features or timelines.

---

!!! info "Before you vote"
    This poll runs until **10 May 2026**. Results will be shared publicly once enough responses are collected.
    If you have specific feedback or want to discuss findings, use [GitHub Discussions](https://github.com/mick-gsk/drift/discussions).

---

<!-- TALLY EMBED — SETUP INSTRUCTIONS
     1. Go to https://tally.so and create a free account
     2. Create a new form with the following structure:
        - Page 1: Introduction text (copy from the plan or the text above)
        - Question 1: "Which of the following would be most valuable to you right now?"
          Type: Multiple choice (allow up to 2 selections)
          Options: [your roadmap candidates — no Drift jargon, max 12 words each]
            + "None of the above / something else"
        - Question 2 (optional): "Anything you'd like to add?" — Short text, optional, max 500 chars
        - Thank-you page: "Thanks — results will be shared at [link] once collected."
     3. In Tally form settings:
        - "Collect respondent email" → OFF
        - "Close submissions after" → set your end date
        - "Allow multiple submissions" → OFF (default: off per browser session)
     4. Click "Share" → "Embed" → copy the iframe HTML
     5. Replace the placeholder below with your actual form ID (the string in the iframe src URL)

     PLACEHOLDER FORM ID: Replace REPLACE_WITH_YOUR_FORM_ID in the two lines below.
-->
<iframe
  data-tally-src="https://tally.so/embed/0QJvKy?alignLeft=1&hideTitle=1&transparentBackground=1&dynamicHeight=1"
  loading="lazy"
  width="100%"
  height="500"
  frameborder="0"
  marginheight="0"
  marginwidth="0"
  title="Drift Community Poll">
</iframe>
<script>
  var d = document,
    w = "https://tally.so/widgets/embed.js",
    v = function () {
      "undefined" != typeof Tally
        ? Tally.loadEmbeds()
        : d
            .querySelectorAll("iframe[data-tally-src]:not([src])")
            .forEach(function (e) {
              e.src = e.dataset.tallySrc;
            });
    };
  if ("undefined" != typeof Tally) v();
  else if (d.querySelector('script[src="' + w + '"]') == null) {
    var s = d.createElement("script");
    s.src = w;
    s.onload = v;
    s.onerror = v;
    d.body.appendChild(s);
  }
</script>

---

**Your privacy:** This poll is anonymous. No email address or account is required. We do not store names or personal identifiers. Responses are aggregated. Form submissions are processed by [Tally.so](https://tally.so/help/privacy-policy) — their privacy policy applies.

**Prefer a different channel?** Leave a comment in [GitHub Discussions](https://github.com/mick-gsk/drift/discussions) or open an issue labeled [`roadmap-input`](https://github.com/mick-gsk/drift/issues/new?labels=roadmap-input).
