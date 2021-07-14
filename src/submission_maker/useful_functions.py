import scipy.stats
import numpy as np

def poisson_interval_RooFit_style(data,CL=0.68):
    down_var=np.nan_to_num(scipy.stats.gamma.ppf((1.-CL)/2.,data))-data
    up_var=np.nan_to_num(scipy.stats.gamma.isf((1.-CL)/2.,data+1))-data
    return np.array([down_var,up_var]).T
