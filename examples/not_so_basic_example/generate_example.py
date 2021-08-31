import json
import numpy as np
import random
import yaml
import itertools
import math
import csv
import array
import ROOT
import os
import tempfile
import TexSoup
import shutil
import glob
import matplotlib.pyplot as plt

def acc_eff_UL_plot_making(grid,z_values,save_name,title=""):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    plt.plot(grid[:,0],grid[:,1],'bo')
    for mt,mn in grid:
        label = "{:.2f}".format(z_values[f"{mt}_{mn}"])
        plt.annotate(label, 
                     (mt,mn), 
                     textcoords="offset points", 
                     xytext=(0,10),
                     fontsize=12,
                     color='gray',
                     ha='center')
    plt.xticks(fontsize=12 )
    plt.yticks(fontsize=12 )
    plt.xlabel(r'$m_{\tilde{t}}$ [GeV]',fontsize=15)
    plt.ylabel(r'$m_{\tilde{\chi}}$ [GeV]',fontsize=15)
    plt.text(1.05,0.5,title,rotation=90, transform=ax.transAxes,fontsize=15)
    plt.gcf().subplots_adjust(bottom=0.15)
    plt.savefig(save_name)

def generate_acc_eff():
    regions=["SRATT","SRATW"]
    grid=np.array([(mt,mn) for mt,mn in itertools.product(range(500,1000,100),range(200,500,50))])
    data_acc={}
    data_eff={}
    random.seed(44)
    for region in regions:
        data_acc[region]={}
        data_eff[region]={}
        for mt,mn in grid:
            data_acc[region][f"{mt}_{mn}"]=random.random()*0.1
            data_eff[region][f"{mt}_{mn}"]=random.random()*1.2
        acc_eff_UL_plot_making(grid,{key:value*100 for key,value in data_acc[region].items()},f"acceptance_example_{region}.pdf",title="Acceptance x 100")
        acc_eff_UL_plot_making(grid,{key:value*100 for key,value in data_eff[region].items()},f"efficiency_example_{region}.pdf",title="Efficiency x 100")

    with open("acc_example.json",'w') as output:
        json.dump(data_acc, output,indent=4)
    with open("eff_example.yaml",'w') as output:
        yaml.dump(data_eff, output)
   
def generate_upper_limits():
    regions=["SRATT","SRATW"]
    grid=np.array([(mt,mn) for mt,mn in itertools.product(range(500,1000,100),range(200,500,50))])
    random.seed(44)
    for region in regions:
        results={"mt":[],"mn":[],"UL_obs":[],"UL_exp":[]}
        tmp_dict_obs={}
        tmp_dict_exp={}
        for mt,mn in grid:
            results["mt"].append(mt)
            results["mn"].append(mn)
            results["UL_obs"].append(1000*random.uniform(0.5,1.5)*math.exp(-mt/100.)*math.exp(-(mt-mn)/1000))
            tmp_dict_obs[f"{mt}_{mn}"]=results["UL_obs"][-1]
            results["UL_exp"].append(1000*random.uniform(0.5,1.5)*math.exp(-mt/100.)*math.exp(-(mt-mn)/1000))
            tmp_dict_exp[f"{mt}_{mn}"]=results["UL_exp"][-1]
        acc_eff_UL_plot_making(grid,tmp_dict_obs,f"upper_limit_example_{region}_obs.pdf",title=f"upper limit (obs) [fb]")
        acc_eff_UL_plot_making(grid,tmp_dict_exp,f"upper_limit_example_{region}_exp.pdf",title=f"upper limit (exp) [fb]")

        with open(f'upper_limit_example_{region}.csv',"w") as csvfile:
            csv_writer=csv.writer(csvfile)
            csv_writer.writerow(results.keys())
            for index in range(len(results['mt'])):
                csv_writer.writerow([results["mt"][index],
                                     results["mn"][index],
                                     results["UL_obs"][index],
                                     results["UL_exp"][index]])


def generate_kin_plots():
    random.seed(44)
    regions={"SRATT":0.5,"SRATW":2}
    for region,scale in regions.items():
        bins=[(x,x+100) for x in range(500,1000,100)]
        low_bins=array.array('f',[x[0] for x in bins]+[bins[-1][1]])
        SM=[10000*scale*random.uniform(0.5,1.5)*math.exp(-bin[0]/100) for bin in bins]
        SM_stat=[0.1*math.sqrt(x) for x in SM] #MC stat
        SM_syst=[random.uniform(0.5,0.9)*x for x in SM_stat]
        SM_total=[math.sqrt(x**2+y**2) for x,y in zip(SM_stat,SM_syst)]
        data=[int(random.gauss(central_value,error)) for central_value,error in zip(SM,SM_stat)]
        signal=[random.uniform(0.5,1.5)*3*scale for x in range(len(bins))]
        h_data=ROOT.TH1F("data","data",len(bins),low_bins)
        h_SM_total=ROOT.TH1F("SM_total","SM_total",len(bins),low_bins)
        h_SM_total_up=ROOT.TH1F("SM_total_up","SM_total_up",len(bins),low_bins)
        h_SM_total_down=ROOT.TH1F("SM_total_down","SM_total_down",len(bins),low_bins)
        h_SM_stat=ROOT.TH1F("SM_stat","SM_stat",len(bins),low_bins)
        h_signal=ROOT.TH1F("signal","signal",len(bins),low_bins)
        for n in range(len(bins)):
            h_data.SetBinContent(n+1,data[n])
            h_SM_total.SetBinContent(n+1,SM[n])
            h_SM_total.SetBinError(n+1,SM_total[n])
            h_SM_total_up.SetBinContent(n+1,SM[n]+SM_total[n])
            h_SM_total_down.SetBinContent(n+1,SM[n]-SM_total[n])
            
            h_SM_stat.SetBinContent(n+1,SM[n])
            h_SM_stat.SetBinError(n+1,SM_stat[n])
            h_signal.SetBinContent(n+1,signal[n])
        h_data_RooHist=ROOT.RooHist(h_data)

        rfile=ROOT.TFile(f"kin_{region}_example.root","RECREATE")
        rfile.cd()
        h_data_RooHist.Write("h_obsData")
        h_SM_total.Write("SM_total")
        h_SM_stat.Write("SM_stat")
        h_signal.Write("sig")
        rfile.Close()

        # Plot the contours
        c1=ROOT.TCanvas(f"towards_{region}","N-1 plot in {region}",800,600)
        h_data_RooHist.SetTitle("")
        h_data_RooHist.GetXaxis().SetTitle('E^{miss}_{T} [GeV]')
        h_data_RooHist.GetYaxis().SetTitle('# Events')
        h_data_RooHist.SetLineWidth(3)
        h_data_RooHist.SetLineColor(ROOT.kBlack)
        h_data_RooHist.Draw("ap")

        h_SM_total_up.SetFillColorAlpha(ROOT.kRed,0.4)
        h_SM_total_up.SetLineWidth(0);
        h_SM_total_up.Draw("same hist")

        h_SM_total_down.SetFillColorAlpha(ROOT.kWhite,1.0)
        h_SM_total_down.SetLineWidth(0);
        h_SM_total_down.Draw("same hist")

        h_data_RooHist.Draw("p same")

        h_SM_total.SetLineColor(ROOT.kRed)
        h_SM_total.SetLineWidth(3)
        h_SM_total.Draw("same hist")
        
        h_signal.Draw("same")
        h_signal.SetLineColor(ROOT.kBlue)
        h_signal.SetLineWidth(3)
        h_signal.SetLineStyle(9)
        h_signal.Draw("same histo")

        legend = ROOT.TLegend(0.6,0.7,0.9,0.9);
        legend.AddEntry(h_data_RooHist,"Data",'lep')
        legend.AddEntry(h_SM_total,"SM",'l')
        legend.AddEntry(h_SM_total_up,"stat+syst",'f')
        legend.AddEntry(h_signal,"SUSY",'l')
        legend.Draw("same")
        
        c1.SaveAs(f"kin_{region}_example.pdf")
        #break
def generate_contour_plots():
    np.random.seed(44)
    # Generate dummy data for contours
    xvals=np.linspace(500,900,25)
    yvals=np.where(xvals<700,((900/math.sqrt(3))*np.sin((xvals-100.)*np.pi/1600.)),(900*np.sin((900.-xvals)*np.pi/1200.)))
    contour_exp=ROOT.TGraph(len(xvals),xvals,yvals)
    xvals_obs=xvals
    yvals_obs=yvals*np.random.uniform(0.9,1.1,len(yvals))
    contour_obs=ROOT.TGraph(len(xvals_obs),xvals_obs,yvals_obs)
    contour_obs.SetTitle("")
    contour_obs.GetXaxis().SetTitle('m_{#tilde{t}} [GeV]')
    contour_obs.GetYaxis().SetTitle('m_{#tilde{\chi}} [GeV]')

    # Save the contours
    rfile=ROOT.TFile(f"exclusion_example.root","RECREATE")
    rfile.cd()
    contour_obs.Write("Obs")
    contour_exp.Write("Exp")
    rfile.Close()

    # Plot the contours
    c1=ROOT.TCanvas("excl_contours","Exclusion contours",800,600)
    contour_obs.Draw()
    contour_obs.SetLineWidth(3)
    contour_obs.SetLineColor(ROOT.kRed)
    contour_exp.Draw("same")
    contour_exp.SetLineWidth(3)
    contour_exp.SetLineStyle(10)
    legend = ROOT.TLegend(0.6,0.75,0.9,0.9);
    legend.AddEntry(contour_obs,"Obs",'l')
    legend.AddEntry(contour_exp,"Exp",'l')
    legend.Draw("same")
    c1.SaveAs("exclusion_example.pdf")


def generate_cutflow_tables():
    ts=TexSoup.TexSoup(open("cutflow_example.tex"))
    tabulars=ts.find_all(['tabular*','tabular'])
    for index,table in enumerate(tabulars):
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(str(tabulars[index]))
            os.system(r"pdflatex '\documentclass[varwidth]{standalone}\begin{document}\input{"+path+r"}\end{document}'")
            print(r"pdflatex '\documentclass[varwidth]{standalone}\begin{document}\input{"+path+r"}\end{document}'")
            shutil.move("texput.pdf",f"cutflow_table_{index}.pdf")
            for filePath in glob.glob("texput.*"):
                try:
                    os.remove(filePath)
                except:
                    print("Error while deleting file : ", filePath)
        finally:
            os.remove(path)

generate_acc_eff()
generate_upper_limits()
generate_kin_plots()   
generate_contour_plots()
generate_cutflow_tables()
