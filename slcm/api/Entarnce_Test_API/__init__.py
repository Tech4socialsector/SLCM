# Package initializer for the "Entarnce Test API" module.
# This allows Python to treat the directory as a package so that
# Frappe can import modules from it using the sanitized name
# (spaces converted to underscores).
#
# No special initialization is required; the presence of this file
# is sufficient.  If you want to expose symbols at package level,
# you can import them here.

from __future__ import unicode_literals

# Optionally expose the submodule as an attribute for convenience.
# from . import entrance_test_result
