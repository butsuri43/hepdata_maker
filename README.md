# hepdata submission maker

Package to help creating and verifying submissions.

# Usage

```
Usage: hepdata_maker [OPTIONS] STEERING_SCRIPT

Options:
--help  Show this message and exit.

Commands:
  check-schema
  check-table	
  create-submission
  
```

currently can only check the steering file schema (for now identity) and  create submission file assuming it gets a correct steering file. 

Intended usecases:

* verify steering screept schema
* verify availability of inputs requested in steering script
* attempt loading a variable of a given table in the steering script 
* attempt to load a given table provided the steering script
* load all the tables from the steering script and create an internal submission object (that can be usef for checks and or record creation)
* create submission file based on the submission object loaded
* check validity of internal submission object with group dependant checks
* check validity of submission files (based on hepdata_validator) 

## Examples

Two examples currently are available:
* stop0L (all table types but not full submission yet):
> run:
> ```
> hepdata_maker create-submission examples/stop0L/submissions_config.json
> ```
> this produces output in `submission_files` as well as `submission.tar.gz`, which is the tar-archive of the former one.
> The output loaded to hepdata can be seen here: https://www.hepdata.net/record/sandbox/1623174132

* stopZh:
> run:
> ```
> hepdata_maker create-submission examples/stopZh/submissions_config.json
> ```
> this produces output in `submission_files`as well as `submission.tar.gz`, which is the tar-archive of the former one.
> The output loaded to hepdata can be seen here:
> https://www.hepdata.net/record/sandbox/1623246991

