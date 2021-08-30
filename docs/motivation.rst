Motivation
===============

Why to use hepdata_maker?
-------------------------

Are you finishing an analysis and was asked to prepare HEPData record? You want to move on with other projects without spending much time on learning intricacies of HPEPData? Converting your data file manually? Waiting for you upload to HEPData to be processed just to end with an error? Or you do not know where to start with your HEPData submission making? If yes, then `hepdata_maker` is for you!

`hepdata_maker` attempts to fill the gaps left by other exisiting libraries, i.e. `hepdata <https://gitlab.com/cholmcc/hepdata>`_ and `hepdata_lib <https://github.com/HEPData/hepdata_lib/>`_, used for HEPData submissions making. The advatages of `hepdata_maker` are:

  - easy to use command line interface,
  - no need to write code (everything is controlled from a json `steering_file`),
  - supports common data formats, i.e. `ROOT`, `json`, `yaml`, `csv` and `tex`,
  - clear off-line record overview,
  - in-house record validations,
  - basic table of content creation for your record,
  - allows for clear version control of your submission. 


To come
-------
.. note:: This is for now still a wishlist
	  
Original idea behind `hepdata_maker` was to provide a framework for automated internal consistency checks of records. Things like:

   - likelihood vs kinematic table cross check (e.g do yields match between kinematic tables and regions specified in likelihoods)
   - likelihood vs upper-limit table checks
   - upper-limits vs exclusion contour checks
   - cutflows vs kinematic tables, etc.

These types of checks are not often performed separately for each analysis and thus often not very consistent between echother. 
