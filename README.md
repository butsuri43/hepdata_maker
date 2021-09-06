# hepdata_maker

Package to help creating and verifying HEPData submissions.


hepdata_maker attempts to fill the gaps left by other exisiting libraries, i.e. [hepdata](https://gitlab.com/cholmcc/hepdata) and [hepdata_lib](https://github.com/HEPData/hepdata_lib), used for HEPData submissions making. The advatages of hepdata_maker are:

- easy to use command line interface,
- no need to write code (everything is controlled from a json steering_file),
- supports common data formats, i.e. ROOT, json, yaml, csv and tex,
- clear off-line record overview,
- off-line record validations,
- basic table of content creation for your record,
- allows for clear version control of your submission.

# Installation

In principle just:
```
pip3 install hepdata-maker
```

but the package require ROOT and ImageMagick. See documentaion for various run options.

# Usage
```
Usage: hepdata_maker [OPTIONS] COMMAND [ARGS]...

  hepdata_maker base CLI entry

Options:
  --version                       Show the version and exit.
  --log-level [CRITICAL|ERROR|WARNING|INFO|DEBUG|NOTSET]
                                  set log level.
  -h, --help                      Show this message and exit.

Commands:
  check-schema              Check STEERING_FILE against hepdata_maker's...
  check-table               Print out informations stored in selected...
  check-variable            Create variable (1-D numpy array) based on...
  create-steering-file      Create a steering_file based on pdf/png and...
  create-submission         Create HEPdata submission files using...
  create-table-of-content   Create a table of content for all the tables...
  hepdata-to-steering-file  Create `hepdata_maker` steering_file from...
  validate-submission       Validate HEPdata submission files located in...
```

currently can only check the steering file schema (for now identity) and  create submission file assuming it gets a correct steering file. 

---
**NOTE**

Package still in active development. 

---

# Acknowledgements

Many thanks to Lukas Heinrich for very useful discussions and technical suggestions.