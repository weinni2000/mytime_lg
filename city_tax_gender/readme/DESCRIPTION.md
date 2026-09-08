This module adds a "Calculated Gender" AI Property to contacts
(``res.partner``).

Rather than adding a new field, it plugs into the generic Properties field
that ``res.partner`` already exposes (visible near the top of every
contact form, and used for ad-hoc custom properties). The property is
filled in automatically by the AI Fields cron from the guest's name, the
same way city_tax's existing "Anrede (AI)" field works.
