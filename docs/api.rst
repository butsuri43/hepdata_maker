Python API
==========

Main Submission classes
-----------------------

.. currentmodule:: hepdata_maker.Submission

.. autosummary::
   :toctree: _generated
   :recursive:

   Submission
   Table
   Variable
   Uncertainty

Useful functions
-----------------------
Functions that can be used in transformations,
referenced as 'ufs.'

.. currentmodule:: hepdata_maker.useful_functions

.. autosummary::
   :toctree: _generated
   :recursive:

   poisson_interval_RooFit_style

Data loading
-----------------------
.. currentmodule:: hepdata_maker.variable_loading
.. autosummary::
   :toctree: _generated
   :recursive:
   
   check_if_file_exists_and_readable
   decode_json_array
   get_array_from_csv
   get_array_from_json
   get_array_from_root
   get_array_from_tex
   get_array_from_yaml
   get_list_of_objects_in_root_file
   get_object_class
   get_table_from_tex
   get_variable_steering_snipped
   open_data_file
   read_data_file
   string_list_available_objects_in_root_file
   yaml_ordered_safe_load
   yaml_ordered_safe_load_all

Checks
-----------------------
.. note:: The functionality in this module adopted from: https://hepdata-submission.readthedocs.io/en/latest/_downloads/3623abae3e9b3aa92c8493b05315cc7e/check.py
.. currentmodule:: hepdata_maker.checks
.. autosummary::
   :toctree: _generated
   :recursive:

   validate_data_yaml
   validate_data_file
   validate_submission

Utils
-----
.. currentmodule:: hepdata_maker.utils
.. autosummary::
   :toctree: _generated
   :recursive:

   merge_dictionaries
   load_schema
   check_schema
   resolve_file_name
   objdict
   get_available_tables
   get_requested_table_list
