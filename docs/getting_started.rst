Getting started
===============

Installation
------------

To use `hepdata_maker`, first install it using pip (inside a virtual env?!):

.. code-block:: console

   pip3 install hepdata_maker

Apart from python libraries installed with pip `hepdata_maker` needs:
  - ROOT (with Python3.7+ support)
  - ImageMagick

.. note::
   The external dependancies are required by `hepdata_lib <https://github.com/HEPData/hepdata_lib>`_ used internally for record creation. Support: `issue to switch to uproot <https://github.com/HEPData/hepdata_lib/issues/108>`_ for this to change.


You can use also following docker images to reduce the need for setup:

  - ``butsuri43/hepdata_submission_docker`` -- in house docker image
  - ``clelange/hepdata_lib`` -- currently compatible alternative from developers of `hepdata_lib <https://github.com/HEPData/hepdata_lib>`_.
    
Running with docker
-------------------

1) Run docker container:

   .. code-block:: Bash

      # Run docker with volume mounting and with your user id
      $ docker run -it --rm -v /abs/path/to/dir/with/your/submission_data:/workdir -u $(id -u):$(id -g) butsuri43/hepdata_submission_docker /bin/bash

2) Within the container install the library

   .. code-block:: Bash

      (docker)$ cd /workdir
      # create & start virtual environment
      (docker)$ python3 -m venv hepdata_env
      (docker)$ source hepdata_env/bin/activate
      # install hepdata_maker inside the virtual environment:
      (hepdata_env)$ pip3 install hepdata_maker

3) You have now the code setup, run it, for example:

   .. code-block:: Bash

      (hepdata_env)$ hepdata-maker --help

4) On docker restart you can reuse the environment created:

   .. code-block:: Bash

      # Run docker with volume mounting and with your user id
      $ docker run -it --rm -v /abs/path/to/dir/with/your/submission_data:/workdir -u $(id -u):$(id -g) butsuri43/hepdata_submission_docker /bin/bash
      # source the saved environment
      (docker)$ cd /workdir
      (docker)$ source hepdata_env/bin/activate
      # and use hepdata_maker! 
      (hepdata_env)$ hepdata-maker --help


Running on lxplus (with singularity)
------------------------------------

On lxplus one can run docker images through singularity.  Since the docker image here is large, if you intend to use the image a few times it is best to build and save singularity-native '.sif' file.

1) setup directory where images are cached by singularity (default is in your AFS home-directory, which would be full in no time if you leave it this way!):

   .. code-block:: Bash
		   
      (lxplus)$ export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"

mind also that you should not place the cache in /afs or /eos as this will not build the image correctly (stick to /tmp/ dir as above!)

2) Build singularity .sif file:

   .. code-block:: Bash

      (lxplus)$ singularity build /eos/user/some/location/on/your/eos/lqcombo-docker-4f842318.sif docker:butsuri43/hepdata_submission_docker

2) Run singularity container:

   .. code-block:: Bash

      (lxplus)$ singularity shell -B /abs/path/to/dir/with/your/submission_data:/workdir /eos/user/some/location/on/your/eos/lqcombo-docker-4f842318.sif   

2) Within the container install the library

   .. code-block:: Bash

      (singularity)$ cd /workdir
      # create & start virtual environment
      (singularity)$ python3 -m venv hepdata_env
      (singularity)$ source hepdata_env/bin/activate
      # install hepdata_maker inside the virtual environment:
      (hepdata_env)$ pip3 install hepdata_maker

4) On singularity restart you can naturally reuse the environment created:

   .. code-block:: Bash

      (lxplus)$ singularity shell -B /abs/path/to/dir/with/your/submission_data:/workdir /eos/user/some/location/on/your/eos/lqcombo-docker-4f842318.sif 
      # source the saved environment
      (singularity)$ cd /workdir
      (singularity)$ source hepdata_env/bin/activate
      # and use hepdata_maker! 
      (hepdata_env)$ hepdata-maker --help

Simple example
--------------

