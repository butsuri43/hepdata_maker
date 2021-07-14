import ROOT
from math import log10, floor
import itertools
import json

def round_sig(x, sig=2):
    if(x==0):
        return 0
    else:
        return round(x, sig-int(floor(log10(abs(x))))-1)

def myround(x, base=50):
    return base * round(x/base)

########## First UL file

rfile=ROOT.TFile("../rawFiles/UpperLimitPlots/BestExpected_UL.root")
canvas=rfile.Get("c1")
primList=canvas.GetListOfPrimitives()

h_UL=None
for obj in primList:
    if(obj.GetName()=='h_UL'):
        h_UL=obj

data=[]
if(h_UL):
    xaxis=h_UL.GetXaxis()
    yaxis=h_UL.GetYaxis()
    for binx,biny in itertools.product(range(h_UL.GetNbinsX()),range(h_UL.GetNbinsY())):
        bin=h_UL.GetBin(binx,biny)
        if(h_UL.GetBinContent(bin)!=0):
            data.append({"mt1":myround(xaxis.GetBinCenter(binx)),"mn2":myround(yaxis.GetBinCenter(biny)),"UL":round_sig(h_UL.GetBinContent(bin))})
    with open('../rawFiles/UpperLimitPlots/BestExpected_UL.json', 'w') as outfile:
        json.dump(data, outfile,indent=4)
########## END of First UL file

########## Second UL file

rfile=ROOT.TFile("../rawFiles/UpperLimitPlots/BestExpected_T2T2_UL.root")
canvas=rfile.Get("c1")
primList=canvas.GetListOfPrimitives()

h_UL=None
for obj in primList:
    if(obj.GetName()=='h_UL'):
        h_UL=obj

data=[]
if(h_UL):
    xaxis=h_UL.GetXaxis()
    yaxis=h_UL.GetYaxis()
    for binx,biny in itertools.product(range(h_UL.GetNbinsX()),range(h_UL.GetNbinsY())):
        bin=h_UL.GetBin(binx,biny)
        if(h_UL.GetBinContent(bin)!=0):
            data.append({"mt2":myround(xaxis.GetBinCenter(binx)),"mn1":myround(yaxis.GetBinCenter(biny)),"UL":round_sig(h_UL.GetBinContent(bin))})
    with open('../rawFiles/UpperLimitPlots/BestExpected_T2T2_UL.json', 'w') as outfile:
        json.dump(data, outfile,indent=4)
########## END of Second UL file
