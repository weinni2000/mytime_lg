=================
Industry Adaption
=================

Local adaptions to the Odoo industry modules, kept out of the upstream
``industry`` repository.

Functionality
=============

* Drops the ``x_resource_id`` column from the rental order wizard list.
* Restores missing selection XML IDs of ``industry_real_estate`` on install,
  so a later upgrade updates those rows instead of failing on the unique
  constraint of ``(field_id, value)``.

Installation
============

``industry_real_estate`` must be installed from the addons path. A module
installed from a zip file (``imported`` set in ``ir_module_module``) is never
upgraded by Odoo, so upstream changes are silently skipped. Check and fix it
with::

    UPDATE ir_module_module
       SET imported = false, application = false
     WHERE name = 'industry_real_estate';

Install this module before upgrading ``industry_real_estate``.
