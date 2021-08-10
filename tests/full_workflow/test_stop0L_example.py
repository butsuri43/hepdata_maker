import tarfile
import os.path
import re

tar_file_path="submission.tar.gz"
expected_yamls=['acc_srat0.yaml',
                'eff_srbtt.yaml',
                'submission.yaml',
                'stop_xsecupperlimit_exp.yaml',
                'stop_exp.yaml',
                'sratw_metsigst.yaml',
                'stop_xsecupperlimit_obs.yaml',
                'acc_srbtt.yaml',
                'acc_srbtw.yaml',
                'stop_obs.yaml',
                'acc_srbt0.yaml',
                'acc_sratt.yaml',
                'acc_sratw.yaml',
                'eff_srat0.yaml',
                'eff_sratt.yaml',
                'eff_sratw.yaml',
                'eff_srbtw.yaml',
                'eff_srbt0.yaml',
                'cutflow_sratt.yaml',
                'overview.yaml']
expected_pngs=['figaux_03b.png',
              'thumb_fig_12a.png',
              'thumb_tabaux_01.png',
              'thumb_figaux_01a.png',
              'thumb_figaux_03a.png',
              'thumb_fig_13a.png',
              'tabaux_01.png',
              'figaux_01a.png',
              'figaux_01b.png',
              'fig_13a.png',
              'figaux_03a.png',
              'thumb_figaux_02a.png',
              'thumb_figaux_03b.png',
              'thumb_figaux_02b.png',
              'thumb_figaux_01b.png',
              'figaux_02b.png',
              'fig_12a.png',
              'figaux_02a.png']

if(not os.path.isfile(tar_file_path)):
    raise IOError("Cannot retrieve submission.tar.gz. Is artifact correctly created?")
my_tar = tarfile.open(tar_file_path)
names=my_tar.getnames()
basenames=[os.path.basename(x) for x in names]

yaml_files=[x for x in basenames if re.match(".*.yaml$",x)]
png_files=[x for x in basenames if re.match(".*.png$",x)]

def diff(current,expected):
    set1=set(expected)-set(current)
    set2=set(current)-set(expected)
    return set1.union(set2)

def print_file_diff(current,expected):
    print(f"current: {current}")
    print(f"expected: {expected}")
    print(f"diff: {diff(current,expected)}")

if(len(yaml_files)!=len(expected_yamls)):
    print_file_diff(yaml_files,expected_yamls)
    raise ValueError(f"Different number of yaml files expected! Expected {len(expected_yamls)}, is: {len(yaml_files)}")
if(len(png_files)!=len(expected_pngs)):
    print_file_diff(png_files,expected_pngs)
    raise ValueError(f"Different number of png files expected! Expected {len(expected_pngs)}, is: {len(png_files)}")
if(set(yaml_files)!=set(expected_yamls)):
    print_file_diff(yaml_files,expected_yamls)
    raise ValueError("Different names expected for yaml files!")
if(set(png_files)!=set(expected_pngs)):
    print_file_diff(png_files,expected_pngs)
    raise ValueError("Different names expected for png files!")
