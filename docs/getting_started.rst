Getting started
===============

Installation
------------

To use `hepdata_maker`, first install it using pip (inside a virtual env?!):

.. code-block:: console

   pip3 install hepdata-maker

Apart from python libraries installed with pip `hepdata_maker` needs:
  - ROOT (with Python3.7+ support)
  - ImageMagick

.. note::
   The external dependancies are required by `hepdata_lib <https://github.com/HEPData/hepdata_lib>`_ used internally for record creation. Support: `issue to switch to uproot <https://github.com/HEPData/hepdata_lib/issues/108>`_ for this to change.


You can use also following docker images to reduce the need for setup:

  - ``butsuri43/hepdata_maker`` -- docker image with `hepdata_maker` pre-installed with all dependancies,
  - ``butsuri43/hepdata_submission_docker`` -- docker image with required packages but without the `hepdata_maker` (install it through pip)
  - ``clelange/hepdata_lib`` -- currently compatible alternative from developers of `hepdata_lib <https://github.com/HEPData/hepdata_lib>`_ (requires installation of `hepdata_maker` through pip).
    
Running with docker
-------------------

1) Run docker container:

   .. code-block:: Bash

      # Run docker with volume mounting and with your user id
      $ docker run -it --rm -v /abs/path/to/dir/with/your/submission_data:/workdir -u $(id -u):$(id -g) butsuri43/hepdata_maker /bin/bash

2) Within the container you have the code setup. You can run it for example:

   .. code-block:: Bash

      (docker)$ cd /workdir
      (docker)$ hepdata-maker --help

Running on lxplus (with singularity)
------------------------------------

On lxplus one can run docker images through singularity.  Since the docker image here is large, if you intend to use the image a few times it is best to build and save singularity-native '.sif' file.

1) setup directory where images are cached by singularity (default is in your AFS home-directory, which would be full in no time if you leave it this way!):

   .. code-block:: Bash
		   
      (lxplus)$ export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"

mind also that you should not place the cache in /afs or /eos as this will not build the image correctly (stick to /tmp/ dir as above!)

2) Build singularity .sif file:

   .. code-block:: Bash

      (lxplus)$ singularity build /eos/user/some/location/on/your/eos/hepdata_maker.sif docker:butsuri43/hepdata_maker

2) Run singularity container:

   .. code-block:: Bash

      (lxplus)$ singularity shell -B /abs/path/to/dir/with/your/submission_data:/workdir /eos/user/some/location/on/your/eos/hepdata_maker.sif   

3) You can start with submission making from within the container:

   .. code-block:: Bash

      (singularity)$ cd /workdir
      (docker)$ hepdata-maker --help

4) On singularity restart you can naturally reuse the environment created:

   .. code-block:: Bash

      (lxplus)$ singularity shell -B /abs/path/to/dir/with/your/submission_data:/workdir /eos/user/some/location/on/your/eos/hepdata_maker.sif 
      (singularity)$ cd /workdir
      (singularity)$ hepdata-maker --help

Getting started with record making
----------------------------------

At the core of `hepdata_maker` lies 'steering_file' which is a json file containig all relevant information needed for record creation (from table names to how to interprete different input files with raw data). By far the easiest way to start with your record is by generating the steering script using ``hepdata_maker create-steering-file`` command.

.. _Example1_reference:

Example1- root
^^^^^^^^^^^^^^

In this example we will use files that can be download from here: :download:`example1.tar.gz <../examples/example1.tar.gz>`.
It contains a directory with two files:

.. code-block:: Bash

   $ tar -zxvf example1.tar.gz
   $ tree example1
   example1
   ├── exclusion_example.pdf
   └── exclusion_example.root

Running command:

.. code-block:: Bash

   $ hepdata_maker create-steering-file -d example1/

which traverse through directory searching for all png/pdf files around which tables are created,
produces `steering_file.json`:

.. literalinclude:: ../examples/example1_result/steering_file.json

In this example, since, on top of the the ``exclusion_example.pdf``, program finds ``exclusion_example.root`` with matching basename to the pdf file, it interpret this as data file and attempts to provide commands to read information stored inside.

.. note:: ROOT files can have multiple histograms/graphs to be read. `hepdata_maker` will try to read them and provide example only for one that works (or skip entirely if it cannot read .root file correctly).

Now, with ``hepdata_maker check-table`` command we can check what informations are stored in the table

.. code-block:: Bash

   $ hepdata_maker check-table steering_file.json

which should be something like this:

.. literalinclude:: ../examples/example1_result/check_table.out

.. note:: The information is exact what will appear in HEPData up to rounding. TODO to fix the bahaviour.

Now we can create HEPData submission files:

.. code-block:: Bash

   $ hepdata_maker create-submission steering_file.json

will create directory `submission_files` and a tarball `submission.tar.gz` containing the directory.

When the tarball is uploaded to HEPData it will yield something like: `this example1 record <https://www.hepdata.net/record/sandbox/1630351529?table=exclusion_example>`_.

.. _Example2_reference:

Example2
^^^^^^^^
In this example we will use files that can be download from here: :download:`example2.tar.gz <../examples/example2.tar.gz>`.
It contains a directory with three files, two of them being the same as in :ref:`Example1_reference`:

.. code-block:: Bash

   $ tar -zxvf example2.tar.gz
   $ tree example2
   example2
   ├── exclusion_example.pdf
   ├── exclusion_example.root
   └── exclusion_example.txt

Running command:

.. code-block:: Bash

   $ hepdata_maker create-steering-file -d example2/

produces the following `steering_file.json`:

.. literalinclude:: ../examples/example2_result/steering_file.json

This time, the table's ``title`` filed points to the txt file. When creating HEPData submission:

.. code-block:: Bash

   $ hepdata_maker create-submission steering_file.json

`hepdata_maker` will recognise that this field points to a file and will use information stored inside it.

When the resulting tarball is uploaded to HEPData it will yield something like: `this example2 record <https://www.hepdata.net/record/sandbox/1630354586?table=exclusion_example>`_.

.. _Example3_reference:

Example3
^^^^^^^^

In this example we will use files that can be download from here: :download:`example3.tar.gz <../examples/example3.tar.gz>`.
It contains a directory with four files:

.. code-block:: Bash

   $ tar -zxvf example3.tar.gz
   $ tree example3
   example3
   ├── exclusion_example.pdf
   ├── exclusion_example.root
   ├── exclusion_example_steering.json
   └── exclusion_example.txt

Running command:

.. code-block:: Bash

   $ hepdata_maker create-steering-file -d example2/

we get this time much more concise steering file:

.. literalinclude:: ../examples/example3_result/steering_file.json

which is because files '\*_steering.json' are treated as subset of steering file describing a single table. 
		    
The resulting `steering_file.json` still passes `hepdata_maker`'s schema checks:

.. code-block:: Bash

   $ hepdata_maker check-schema steering_file.json
   ====== checking_schema ======
   Checking schema of steering_file.json.
   All ok!

When HEPData submission files are created,

.. code-block:: Bash

   $ hepdata_maker create-submission steering_file.json

and the resulting tarball is uploaded to HEPData it will yield something like: `this example3 record <https://www.hepdata.net/record/sandbox/1630357014?table=exclusion_example>`_.

.. note:: Mind that data/image/title files in the ``exclusion_example_steering.json`` are given relative to directory from which we execute the commands (or more precisely relative to where the steering file, result of ``hepdata_maker create-steering-file`` is produced). If we, in this example, decide to run ``hepdata_maker create-submission`` from different directory, let's say one up from where steering file is located we need to use ``--data-root`` option to tell relative to which directory resolve names:

	  .. code-block:: Bash

	     $ cd ../
	     $ hepdata_maker create-submission examples/steering_file.json --data-root examples/

.. _Example4_reference:

Example4 - json
^^^^^^^^^^^^^^^

The next example shows how to figure out transformations needed to read json data files. In this example we will use files that can be download from here: :download:`example4.tar.gz <../examples/example4.tar.gz>`.
It contains a directory with two files:

.. code-block:: Bash

   $ tar -zxvf example4.tar.gz
   $ tree example4
   example4/
   ├── acceptance_example_SRATT.pdf
   └── acc_example.json

This time we will not get much if we run ``hepdata_maker create-steering-file`` (since json & pdf have different core names).

.. note:: since ``hepdata_maker create-steering-file`` searches for image files and matching data files, in this case `acc_example.json` will be ignored by it. 

We can instead use ``hepdata_maker check-variable``. Running:

.. code-block:: Bash

   $ hepdata_maker check-variable -f "example4/acc_example.json"

it will raise an error complaining that we have not specified the option 'decode' that (for json) needs to be `jq <https://stedolan.github.io/jq/manual/>`_ command.
It is probably best to find the correct transformation with jq directly, but `hepdata_maker` attempts to be helpful too.

Not knowing where to start we can start with basic 'keys_unsorted':

.. code-block:: Bash

   $ hepdata_maker check-variable -f "example4/acc_example.json" -d "keys_unsorted"

Among other things we can read that this results in two values: ['SRATT' 'SRATW']. Here we are interested in 'SRATT' thus we select it:

.. code-block:: Bash

   $ hepdata_maker check-variable -f "example4/acc_example.json" -d ".['SRATT']"

and get that it holds a dictionary :

.. code-block:: Bash

   {
   "500_200": 0.04085358792544938,
   "500_250": 0.08620366164792732,
   "500_300": 0.022515952057814672,
   "500_350": 0.01166505334428638,
   "500_400": 0.015669033508336382,
   ...
   }

continue like that we can get correct decode formulas for mt, mn and acceptance values:

  - mt: ".['SRATT'] | keys_unsorted[] | split('_')[0]"
  - mn  ".['SRATT'] | keys_unsorted[] | split('_')[0]"
  - acc  ".['SRATT'][]"

.. note:: `jq` requires double quotes (\"), and so does json.
   The above examples would only work with escaped doble-quotes in bash-jq, e.g.:

   .. code-block:: Bash

      $  jq ".[\"SRATT\"] | keys_unsorted[] | split(\"_\")[0]" example4/acc_example.json
      
   To avoid ugly escaping being everywhere `hepdata_maker` replaces internally single quotes with double ones. Let's hope your use case does not need unescaped single-quotes.

Running once again:
.. code-block:: Bash

   hepdata_maker check-variable -f "example4/acc_example.json" -d ".['SRATT'] | keys_unsorted[] | split('_')[0]"

we see `hepdata_maker` suggestion on injection to your steering_script:

.. literalinclude:: ../examples/example4_result/var_mt_suggestion.json

We can then construct full fledge steering_script:

.. literalinclude:: ../examples/example4_result/steering_file.json

The coresponding HEPData tarball yields something like: `this example4 record <https://www.hepdata.net/record/sandbox/1630362142>`_.

.. _Example5_reference:

Example5 - yaml
^^^^^^^^^^^^^^^

In this example we present decoding example for yaml files. We will use files that can be download from here: :download:`example5.tar.gz <../examples/example5.tar.gz>`.
The tarball contains a directory with two files:

.. code-block:: Bash

   $ tar -zxvf example5.tar.gz
   $ tree example5
   example5
   ├── eff_example.yaml
   └── efficiency_example_SRATW.pdf

Yaml files are from the user point of view treated similar to json in `hepdata_maker`.
Therefore, performing a similar excersise to :ref:`Example4_reference` one can get the following steering file:

.. literalinclude:: ../examples/example5_result/steering_file.json

which results in the following HEPData submission: `this example5 record <https://www.hepdata.net/record/sandbox/1630363616>`_.

.. _Example6_reference:

Example6 - tex
^^^^^^^^^^^^^^^

In this example we present decoding example for tex files. We will use files that can be download from here: :download:`example6.tar.gz <../examples/example6.tar.gz>`.

As with other data formats, ``hepdata_maker check-variable`` tries to be helpful and guide the user when tex-file is provided.

When just tex file is provided, without additional information is given:

.. code-block:: Bash

   $ hepdata_maker check-variable -f "example6/cutflow_example.tex"

it will start from complaining about missing ``--tabular-loc-decode`` option (specifying which tabular environment to use from the tex file).

When ``--tabular-loc-decode`` is given, it will ask for ``--decode`` to decode 2-D table into 1-D variable array.

If we want the first column from second tablar environment, without the top row, this is what we need:

.. code-block:: Bash

   hepdata_maker check-variable -f cutflow_example.tex --tabular-loc-decode "latex.find_all(['tabular*','tabular'])[1]" -d "table[1:,0]"

Putting together all variables we can get the following steering file:

.. literalinclude:: ../examples/example6_result/steering_file.json

which results in the HEPData submission: `this example6 record <https://www.hepdata.net/record/sandbox/1630365204>`_.

.. _Example7_reference:

Example7 - csv
^^^^^^^^^^^^^^^
In this example we present decoding example for csv files. We will use files that can be download from here: :download:`example7.tar.gz <../examples/example7.tar.gz>`.

Also for csv files ``hepdata_maker check-variable`` is a good place to start.

.. code-block:: Bash

   $ hepdata_maker check-variable -f "example7/upper_limit_example_SRATT.csv"

After selecting specific columns, it is straightforward to get to:

.. literalinclude:: ../examples/example7_result/steering_file.json

which results in the HEPData submission: `this example7 record <https://www.hepdata.net/record/sandbox/1630367107>`_.

Example8 - full fledged
^^^^^^^^^^^^^^^^^^^^^^^
This example contains several table, with various functionalities of ``hepdata_maker`` presented there. It presents typical tables present in HEPData submission, additional resources and others. It should serve as a reference what is possible. The files can be downloaded :download:`example8.tar.gz <../examples/example8.tar.gz>`.

The tarball contains following files:

.. code-block:: Bash

   example8
   ├── main_steering_file.json
   ├── raw_files
   │   ├── acceptance_example_SRATT.pdf
   │   ├── acceptance_example_SRATW.pdf
   │   ├── acc_example.json
   │   ├── cutflow_example.tex
   │   ├── cutflow_table_0.pdf
   │   ├── cutflow_table_1.pdf
   │   ├── eff_example.yaml
   │   ├── efficiency_example_SRATT.pdf
   │   ├── efficiency_example_SRATW.pdf
   │   ├── exclusion_example.pdf
   │   ├── exclusion_example.root
   │   ├── generate_example.py
   │   ├── kin_SRATT_example.pdf
   │   ├── kin_SRATT_example.root
   │   ├── kin_SRATW_example.pdf
   │   ├── kin_SRATW_example.root
   │   ├── mock_data_tarball.tar.gz
   │   ├── upper_limit_example_SRATT.csv
   │   ├── upper_limit_example_SRATT_exp.pdf
   │   ├── upper_limit_example_SRATT_obs.pdf
   │   ├── upper_limit_example_SRATW.csv
   │   ├── upper_limit_example_SRATW_exp.pdf
   │   └── upper_limit_example_SRATW_obs.pdf
   └── table_steerings
       ├── acc_SRATT_steering.json
       ├── acc_SRATT_title.txt
       ├── acc_SRATW_steering.json
       ├── acc_SRATW_title.txt
       ├── cutflow_SRATT_steering.json
       ├── cutflow_SRATT_title.txt
       ├── cutflow_SRATW_steering.json
       ├── cutflow_SRATW_title.txt
       ├── eff_SRATT_steering.json
       ├── eff_SRATT_title.txt
       ├── eff_SRATW_steering.json
       ├── eff_SRATW_title.txt
       ├── exp_exclusion_steering.json
       ├── exp_exclusion_title.txt
       ├── exp_UL_SRATT_steering.json
       ├── exp_UL_SRATT_title.txt
       ├── exp_UL_SRATW_steering.json
       ├── exp_UL_SRATW_title.txt
       ├── kin_SRATT_steering.json
       ├── kin_SRATT_title.txt
       ├── kin_SRATW_steering.json
       ├── kin_SRATW_title.txt
       ├── obs_exclusion_steering.json
       ├── obs_exclusion_title.txt
       ├── obs_UL_SRATT_steering.json
       ├── obs_UL_SRATT_title.txt
       ├── obs_UL_SRATW_steering.json
       ├── obs_UL_SRATW_title.txt
       └── table_of_content.txt


After creating submission files:

.. code-block:: Bash

    hepdata_maker create-submission main_steering_file.json
		
uploaded results looks like this: `this example8 record <https://www.hepdata.net/record/sandbox/1630400334>`_.
