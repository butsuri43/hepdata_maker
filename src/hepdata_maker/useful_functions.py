import scipy.stats # type: ignore
import numpy as np

def poisson_interval_RooFit_style(data:np.ndarray,
                                  CL:float=0.68) -> np.ndarray:
    """
    get RooFit-style Poisson interval for data in numpy array.
    """
    down_var=np.nan_to_num(scipy.stats.gamma.ppf((1.-CL)/2.,data))-data
    up_var=np.nan_to_num(scipy.stats.gamma.isf((1.-CL)/2.,data+1))-data
    return np.array([down_var,up_var]).T
