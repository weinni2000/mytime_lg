=============
DeepSeek Base
=============

Provides a global DeepSeek API key setting for DeepSeek integrations.

The key is stored as the ``deepseek.api_key`` system parameter. It can be
managed from General Settings or overridden through ``server_environment``
configuration:

.. code-block:: ini

   [ir.config_parameter]
   deepseek.api_key=sk-...

An environment-defined value takes precedence over the database value.
