#include "SimpleAnalysis/AnalysisClass.h"
#include "SimpleAnalysis/METSignificanceCalculator.h"

DefineAnalysis(ttbarMET0L2018)

void ttbarMET0L2018::Init() {
  //Define Signal Regions
  addRegions( { "SRA", "SRATT", "SRATW", "SRAT0" });
  addRegions( { "SRB", "SRBTT", "SRBTW", "SRBT0" });
  addRegions( { "SRC", "SRC1", "SRC2", "SRC3", "SRC4", "SRC5" });
  addRegions( { "SRD", "SRD0", "SRD1", "SRD2" });
    
#ifdef ROOTCORE_PACKAGE_Ext_RestFrames
  LabRecoFrame* LAB = m_RF_helper.addLabFrame("LAB");
  DecayRecoFrame* CM = m_RF_helper.addDecayFrame("CM");
  DecayRecoFrame* S = m_RF_helper.addDecayFrame("S");
  VisibleRecoFrame* ISR = m_RF_helper.addVisibleFrame("ISR");
  VisibleRecoFrame* V = m_RF_helper.addVisibleFrame("V");
  InvisibleRecoFrame* I = m_RF_helper.addInvisibleFrame("I");

  LAB->SetChildFrame(*CM);
  CM->AddChildFrame(*ISR);
  CM->AddChildFrame(*S);
  S->AddChildFrame(*V);
  S->AddChildFrame(*I);

  LAB->InitializeTree();

  InvisibleGroup* INV = m_RF_helper.addInvisibleGroup("INV");
  INV->AddFrame(*I);
  CombinatoricGroup* VIS = m_RF_helper.addCombinatoricGroup("VIS");
  VIS->AddFrame(*ISR);
  VIS->SetNElementsForFrame(*ISR,1,false);
  VIS->AddFrame(*V);
  VIS->SetNElementsForFrame(*V,0,false);

  // set the invisible system mass to zero
  InvisibleJigsaw* InvMass = m_RF_helper.addInvisibleJigsaw("InvMass",kSetMass);
  INV->AddJigsaw(*InvMass);

  // define the rule for partitioning objects between "ISR" and "V"
  MinMassesCombJigsaw* SplitVis = m_RF_helper.addCombinatoricJigsaw("CombPPJigsaw", kMinMasses);
  VIS->AddJigsaw(*SplitVis);
  // "0" group (ISR)
  SplitVis->AddFrame(*ISR, 0);
  // "1" group (V + I)
  SplitVis->AddFrame(*V,1);
  SplitVis->AddFrame(*I,1);

  LAB->InitializeAnalysis();
#endif
}

void ttbarMET0L2018::ProcessEvent(AnalysisEvent *event) {
  // Assume PrimVtx for Truth
  // No Trigger for Truth
  
  // Get Baseline Objects
  auto baseJets = event->getJets(20., 2.8, JVT59Jet);
  auto baseElectrons = event->getElectrons(4.5, 2.47, ELooseBLLH | EZ05mm);
  auto baseMuons = event->getMuons(4.0, 2.7, MuMedium | MuZ05mm);
  
  // Get Truth Met + Object-Based MetSig
  auto metVec = event->getMET();
  float Met = metVec.Pt();
  double MetSig = calcMETSignificance(event);

  // Overlap Removal
  auto radiusCalcLepton = [] (const AnalysisObject& lepton, const AnalysisObject& ) {return std::min(0.4, 0.04 + 10/lepton.Pt());};
  auto muJetSpecial = [] (const AnalysisObject& jet, const AnalysisObject& muon) {
    if (jet.pass(NOT(BTag77MV2c10)) && (jet.pass(LessThan3Tracks) || muon.Pt()/jet.Pt()>0.5)) return 0.2;
    else return 0.;
  };
  baseMuons = overlapRemoval(baseMuons, baseElectrons, 0.01, NOT(MuCaloTaggedOnly));
  baseElectrons = overlapRemoval(baseElectrons, baseMuons, 0.01);
  
  baseJets = overlapRemoval(baseJets, baseElectrons, 0.2, NOT(BTag77MV2c10));
  baseElectrons = overlapRemoval(baseElectrons, baseJets, 0.2);
  
  baseJets = overlapRemoval(baseJets, baseMuons, muJetSpecial, NOT(BTag77MV2c10));
  baseMuons = overlapRemoval(baseMuons, baseJets, 0.2);
  
  baseMuons = overlapRemoval(baseMuons, baseJets, radiusCalcLepton);
  baseElectrons = overlapRemoval(baseElectrons, baseJets, radiusCalcLepton);

  // After OR Baseline Leptons
  int nBaseElectrons = countObjects(baseElectrons, 4.5, 2.47);
  int nBaseMuons = countObjects(baseMuons, 4.0, 2.7);
  int nLep = nBaseElectrons + nBaseMuons;
  auto baseLeptons = baseElectrons + baseMuons;

  // Get signal jets
  auto signalJets = filterObjects(baseJets, 20, 2.8, JVT59Jet);
  int nSignalJets = countObjects(signalJets, 20, 2.8);
  auto nonBJets = filterObjects(signalJets, 20, 2.8, NOT(BTag77MV2c10));
  int nNonBJets = countObjects(nonBJets, 20, 2.8);
  auto signalBJets = filterObjects(signalJets, 20, 2.5, BTag77MV2c10);
  int nBJets = countObjects(signalBJets, 20, 2.5);

  // Check for bad jets after Overlap Removal
  int nBadJets = countObjects(signalJets, 20, 4.5, NOT(LooseBadJet));
  
  // DRBB
  float DRBB = 0;
  if (nBJets > 1) DRBB = signalBJets[1].DeltaR(signalBJets[0]);

  // dPhiJetMet
  double dPhiJetMetMin2 = 0;
  double dPhiJetMetMin3 = 0;
  double dPhiJetMetMin4 = 0;
  if (nSignalJets >= 2) {
    dPhiJetMetMin2 = std::min(fabs(metVec.DeltaPhi(signalJets[0])), fabs(metVec.DeltaPhi(signalJets[1])));
    if (nSignalJets>=3) {
      dPhiJetMetMin3 = std::min(dPhiJetMetMin2, fabs(metVec.DeltaPhi(signalJets[2])));
      if (nSignalJets>=4) {
	dPhiJetMetMin4 = std::min(dPhiJetMetMin3, fabs(metVec.DeltaPhi(signalJets[3])));
      }
    }
  }
  
  // Reclustering
  float AntiKt8M_0 = 0;
  //  float AntiKt8M_1 = 0;
  float AntiKt12M_0 = 0;
  float AntiKt12M_1 = 0;
  auto fatJetsR8 = reclusterJets(signalJets, 0.8, 20., 0.2, 0.00);
  int nFatJetsR8 = countObjects(fatJetsR8, 20, 2.8);
  auto fatJetsR12 = reclusterJets(signalJets, 1.2, 20., 0.2, 0.00);
  int nFatJetsR12 = countObjects(fatJetsR12, 20, 2.8);
  if (nFatJetsR8 > 0) AntiKt8M_0 = fatJetsR8[0].M();
  //if (nFatJetsR8 > 1) AntiKt8M_1 = fatJetsR8[1].M();
  if (nFatJetsR12 > 0) AntiKt12M_0 = fatJetsR12[0].M();
  if (nFatJetsR12 > 1) AntiKt12M_1 = fatJetsR12[1].M();
  

  // Tau veto (Here for bookeeping. The LessOrEq4Tracks flag doesn't actually reject anything)
  float MtTauCand = -1;
  auto tauCands = filterObjects(signalJets, 20, 2.5, LessOrEq4Tracks);
  for (const auto& jet : tauCands) {
    if (jet.DeltaPhi(metVec) < M_PI/5.) {
      MtTauCand = calcMT(jet, metVec);
    }
    if (MtTauCand > 0) break;
  }
  
    
  // Close-by b-jets and MtBMets
  int NCloseByBJets12Leading = 0;
  int NCloseByBJets12Subleading = 0;
  float MtBMin = 0;
  float MtBMax = 0;
  double dPhi_min = 1000.;
  double dPhi_max = 0.;
  if (nBJets >= 2) {
    for (const auto& jet : signalBJets) {
      double dphi = fabs(metVec.DeltaPhi(jet));
      if (dphi < dPhi_min) {
	dPhi_min = dphi;
	MtBMin = calcMT(jet, metVec);
      }
      if (dphi > dPhi_max) {
	dPhi_max = dphi;
	MtBMax = calcMT(jet, metVec);
      }
      if (nFatJetsR12 > 0 && jet.DeltaR(fatJetsR12[0]) <= 1.2)
	NCloseByBJets12Leading++;
      if (nFatJetsR12 > 1 && jet.DeltaR(fatJetsR12[1]) <= 1.2)
	NCloseByBJets12Subleading++;
    }
  }
  
  //Chi2 method (Same as stop0L2015.cxx)
  float realWMass = 80.385;
  float realTopMass = 173.210;
  double Chi2min = DBL_MAX;
  int W1j1_low = -1, W1j2_low = -1, W2j1_low = -1, W2j2_low = -1, b1_low = -1, b2_low = -1;
  double MT2Chi2 = 0;
  if (nSignalJets >= 4 && nBJets >= 2 && nNonBJets >= 2) {
    for (int W1j1 = 0; W1j1 < (int) nNonBJets; W1j1++) { 
      for (int W2j1 = 0; W2j1 < (int) nNonBJets; W2j1++) {
	if (W2j1 == W1j1) continue; 
	for (int b1 = 0; b1 < (int) nBJets; b1++) {
	  for (int b2 = 0; b2 < (int) nBJets; b2++) {
	    if (b2 == b1) continue;
	    double chi21, chi22, mW1, mW2, mt1, mt2;	    
	    if (W2j1 > W1j1) {
	      mW1 = nonBJets[W1j1].M();
	      mW2 = nonBJets[W2j1].M();
	      mt1 = (nonBJets[W1j1] + signalBJets[b1]).M();
	      mt2 = (nonBJets[W2j1] + signalBJets[b2]).M();
	      chi21 = (mW1 - realWMass) * (mW1 - realWMass) / realWMass + (mt1 - realTopMass) * (mt1 - realTopMass) / realTopMass;
	      chi22 = (mW2 - realWMass) * (mW2 - realWMass) / realWMass + (mt2 - realTopMass) * (mt2 - realTopMass) / realTopMass;
	      if (Chi2min > (chi21 + chi22)) {
		Chi2min = chi21 + chi22;
		if (chi21 < chi22) {
		  W1j1_low = W1j1;
		  W1j2_low = -1;
		  W2j1_low = W2j1;
		  W2j2_low = -1;
		  b1_low = b1;
		  b2_low = b2;
		}
		else {
		  W2j1_low = W1j1;
		  W2j2_low = -1;
		  W1j1_low = W2j1;
		  W1j2_low = -1;
		  b2_low = b1;
		  b1_low = b2;
		}
	      }
	    }
	    if (nNonBJets < 3)
	      continue;
	    for (int W1j2 = W1j1 + 1; W1j2 < nNonBJets; W1j2++) {
	      if (W1j2 == W2j1) continue;
	      //try bll,bl top candidates
	      mW1 = (nonBJets[W1j1] + nonBJets[W1j2]).M();
	      mW2 = (nonBJets[W2j1]).M();
	      mt1 = (nonBJets[W1j1] + nonBJets[W1j2] + signalBJets[b1]).M();
	      mt2 = (nonBJets[W2j1] + signalBJets[b2]).M();
	      chi21 = (mW1 - realWMass) * (mW1 - realWMass) / realWMass + (mt1 - realTopMass) * (mt1 - realTopMass) / realTopMass;
	      chi22 = (mW2 - realWMass) * (mW2 - realWMass) / realWMass + (mt2 - realTopMass) * (mt2 - realTopMass) / realTopMass;
	      if (Chi2min > (chi21 + chi22)) {
		Chi2min = chi21 + chi22;
		if (chi21 < chi22) {
		  W1j1_low = W1j1;
		  W1j2_low = W1j2;
		  W2j1_low = W2j1;
		  W2j2_low = -1;
		  b1_low = b1;
		  b2_low = b2;
		}
		else {
		  W2j1_low = W1j1;
		  W2j2_low = W1j2;
		  W1j1_low = W2j1;
		  W1j2_low = -1;
		  b2_low = b1;
		  b1_low = b2;
		}
	      }
	      if (nNonBJets < 4) continue;
	      //try bll, bll top candidates
	      for (int W2j2 = W2j1 + 1; W2j2 < (int) nNonBJets; W2j2++) {
		if ((W2j2 == W1j1) || (W2j2 == W1j2)) continue;
		if (W2j1 < W1j1) continue; //runtime reasons, we don't want combinations checked twice <--------------------This line should be added
		mW1 = (nonBJets[W1j1] + nonBJets[W1j2]).M();
		mW2 = (nonBJets[W2j1] + nonBJets[W2j2]).M();
		mt1 = (nonBJets[W1j1] + nonBJets[W1j2] + signalBJets[b1]).M();
		mt2 = (nonBJets[W2j1] + nonBJets[W2j2] + signalBJets[b2]).M();
		chi21 = (mW1 - realWMass) * (mW1 - realWMass) / realWMass + (mt1 - realTopMass) * (mt1 - realTopMass) / realTopMass;
		chi22 = (mW2 - realWMass) * (mW2 - realWMass) / realWMass + (mt2 - realTopMass) * (mt2 - realTopMass) / realTopMass;
		if (Chi2min > (chi21 + chi22)) {
		  Chi2min = chi21 + chi22;
		  if (chi21 < chi22) {
		    W1j1_low = W1j1;
		    W1j2_low = W1j2;
		    W2j1_low = W2j1;
		    W2j2_low = W2j2;
		    b1_low = b1;
		    b2_low = b2;
		  }
		  else {
		    W2j1_low = W1j1;
		    W2j2_low = W1j2;
		    W1j1_low = W2j1;
		    W1j2_low = W2j2;
		    b2_low = b1;
		    b1_low = b2;
		  }
		}
	      }
	    }
	  }
	}
      }
    }
    
    AnalysisObject WCand0 = nonBJets[W1j1_low];
    if (W1j2_low != -1) WCand0 += nonBJets[W1j2_low];
    AnalysisObject topCand0 = WCand0 + signalBJets[b1_low];
    
    AnalysisObject WCand1 = nonBJets[W2j1_low];
    if (W2j2_low != -1) WCand1 += nonBJets[W2j2_low];
    AnalysisObject topCand1 = WCand1 + signalBJets[b2_low];
    
    AnalysisObject top0Chi2 = topCand0;
    AnalysisObject top1Chi2 = topCand1;

    double Energy0 = sqrt(173.210 * 173.210 + top0Chi2.Pt() * top0Chi2.Pt());
    double Energy1 = sqrt(173.210 * 173.210 + top1Chi2.Pt() * top1Chi2.Pt());
    AnalysisObject top0(top0Chi2.Px(), top0Chi2.Py(), 0, Energy0, 0, 0, COMBINED, 0, 0);
    AnalysisObject top1(top1Chi2.Px(), top1Chi2.Py(), 0, Energy1, 0, 0, COMBINED, 0, 0);
    MT2Chi2 = calcMT2(top0, top1, metVec);
  }
     
#ifdef ROOTCORE_PACKAGE_Ext_RestFrames
  // RestFrames stuff
  double CA_PTISR=0;
  double CA_MS=0;
  double CA_NbV=0;
  double CA_NjV=0;
  double CA_RISR=0;
  double CA_dphiISRI=0;
  double CA_pTjV4=0;
  double CA_pTbV1=0;
  
  LabRecoFrame* LAB = m_RF_helper.getLabFrame("LAB");
  InvisibleGroup* INV = m_RF_helper.getInvisibleGroup("INV");
  CombinatoricGroup* VIS = m_RF_helper.getCombinatoricGroup("VIS");
  
  LAB->ClearEvent();
  std::vector<RFKey> jetID;
  
  // use transverse view of jet 4-vectors
  for(const auto & jet : signalJets)
    jetID.push_back(VIS->AddLabFrameFourVector(jet.transFourVect()));
  
  INV->SetLabFrameThreeVector(metVec.Vect());
  // std::cout<<"Something happens below that spits out a warning."<<std::endl;

  int m_NjV(0);
  int m_NbV(0);
  int m_NbISR(0);
  double m_pTjV4(0.);
  double m_pTbV1(0);
  double m_PTISR(0.);
  double m_MS(0.);
  double m_RISR(0.);
  double m_dphiISRI(0.);
  

  if (nSignalJets>0) {
    if(!LAB->AnalyzeEvent()) std::cout << "Something went wrong... " << nSignalJets<< std::endl;
  
    DecayRecoFrame* CM = m_RF_helper.getDecayFrame("CM");
    DecayRecoFrame* S = m_RF_helper.getDecayFrame("S");
    VisibleRecoFrame* ISR = m_RF_helper.getVisibleFrame("ISR");
    VisibleRecoFrame* V = m_RF_helper.getVisibleFrame("V");
    InvisibleRecoFrame* I = m_RF_helper.getInvisibleFrame("I");
  
    for(int i = 0; i < nSignalJets; i++) {
      if (VIS->GetFrame(jetID[i]) == *V) { // sparticle group
	m_NjV++;
	if (m_NjV == 4) m_pTjV4 = signalJets[i].Pt();
	if (signalJets[i].pass(BTag77MV2c10) && fabs(signalJets[i].Eta())<2.5) {
	  m_NbV++;
	  if (m_NbV == 1) m_pTbV1 = signalJets[i].Pt();
	}
      } else {
	if (signalJets[i].pass(BTag77MV2c10) && fabs(signalJets[i].Eta())<2.5)
	  m_NbISR++;
      }
    }
  
    // need at least one jet associated with MET-side of event
    if(m_NjV >= 1)
      {
	TVector3 vP_ISR = ISR->GetFourVector(*CM).Vect();
	TVector3 vP_I = I->GetFourVector(*CM).Vect();
      
	m_PTISR = vP_ISR.Mag();
	m_RISR = fabs(vP_I.Dot(vP_ISR.Unit())) / m_PTISR;
      
	m_MS = S->GetMass();
      
	m_dphiISRI = fabs(vP_ISR.DeltaPhi(vP_I));
      
	CA_PTISR=m_PTISR;
	CA_MS=m_MS;
	CA_NbV=m_NbV;
	CA_NjV=m_NjV;
	CA_RISR=m_RISR;
	CA_dphiISRI=m_dphiISRI;
	CA_pTjV4=m_pTjV4;
	CA_pTbV1=m_pTbV1;
      }
  }
#endif

  // Sum Pt Vars
  double Ht = sumObjectsPt(signalJets);
  double HtSig = Met / TMath::Sqrt(Ht);
  //  double sumTagJetPt = sumObjectsPt(signalBJets, 2);

  /////////////////////////////////////
  // End Variable calculations

  //////////////////////////////////////
  // Region Cuts
  bool pre1B4J0L = Met > 250 && nLep == 0 && nSignalJets >= 4 && nBJets >= 1 && signalJets[1].Pt() > 80 && signalJets[3].Pt() > 40 && dPhiJetMetMin2>0.4;
  bool pre2B4J0L = pre1B4J0L && nBJets >= 2 && dPhiJetMetMin4 > 0.4 && MetSig > 5 && MtBMin > 50 && MtTauCand < 0;
  bool pre2B4J0Ltight = pre2B4J0L && MtBMin > 200;
  bool pre2B4J0LtightTT = pre2B4J0Ltight && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>120;
  bool pre2B4J0LtightTW = pre2B4J0Ltight && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>60 && AntiKt12M_1<120;
  bool pre2B4J0LtightT0 = pre2B4J0Ltight && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>0 && AntiKt12M_1<60;
  
  bool SRA = pre2B4J0Ltight && MT2Chi2 > 450 && nFatJetsR12>=2 && AntiKt12M_0>120 && AntiKt8M_0 > 60.00 && MetSig > 25.00 && NCloseByBJets12Leading >= 1;
  bool SRATT = pre2B4J0LtightTT && MT2Chi2 > 450 && AntiKt8M_0 > 60.00 && MetSig > 25.00 && NCloseByBJets12Leading >= 1 && NCloseByBJets12Subleading >= 1 && DRBB > 1.00;
  bool SRATW = pre2B4J0LtightTW && MT2Chi2 > 450 && AntiKt8M_0 > 60.00 && MetSig > 25.00 && NCloseByBJets12Leading >= 1;
  bool SRAT0 = pre2B4J0LtightT0 && MT2Chi2 > 450 && AntiKt8M_0 > 60.00 && MetSig > 25.00 && NCloseByBJets12Leading >= 1;
  
  bool SRB = pre2B4J0Ltight && MtBMax>200 && DRBB>1.4 && nFatJetsR12>=2 && AntiKt12M_0>120 && MT2Chi2<450 && MetSig>14;
  bool SRBTT = SRB && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>120;
  bool SRBTW = SRB && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>60 && AntiKt12M_1<120;
  bool SRBT0 = SRB && nFatJetsR12>=2 && AntiKt12M_0>120. && AntiKt12M_1>0 && AntiKt12M_1<60;

  if (SRA) accept("SRA");
  if (SRATT) accept("SRATT");
  if (SRATW) accept("SRATW");
  if (SRAT0) accept("SRAT0");
  if (SRB) accept("SRB");
  if (SRBTT) accept("SRBTT");
  if (SRBTW) accept("SRBTW");
  if (SRBT0) accept("SRBT0");
  
#ifdef ROOTCORE_PACKAGE_Ext_RestFrames
  bool SRC = pre1B4J0L && CA_NbV >= 2 && MetSig > 5 && CA_NjV >= 4 && CA_pTbV1 > 40 && CA_MS > 400 && CA_dphiISRI > 3.00 && CA_PTISR > 400 && CA_pTjV4 > 50;
  if ( SRC ) accept("SRC");
  if ( SRC && CA_RISR >= 0.30 && CA_RISR <= 0.4) accept("SRC1");
  if ( SRC && CA_RISR >= 0.4 && CA_RISR <= 0.5) accept("SRC2");
  if ( SRC && CA_RISR >= 0.5 && CA_RISR <= 0.6) accept("SRC3");
  if ( SRC && CA_RISR >= 0.6 && CA_RISR <= 0.7) accept("SRC4");
  if ( SRC && CA_RISR >= 0.7) accept("SRC5");
#endif

  bool SRDLoose = nLep == 0 && nBadJets == 0 && Met > 250 && nonBJets.size() > 0 && nonBJets.size() > 0 && nonBJets[0].Pt()>250 && nonBJets[0].DeltaR(metVec) > 2.4 && HtSig > 22;
  bool SRD0 = SRDLoose && nBJets == 0 && dPhiJetMetMin4>0.4 && HtSig > 26;
  bool SRD1 = SRDLoose && nBJets == 1 && fabs(signalBJets[0].Eta())<1.6 && signalBJets[0].DeltaPhi(nonBJets[0])>2.0 && signalBJets[0].DeltaPhi(nonBJets[0])>2.2;
  bool SRD2 = SRDLoose && nBJets >= 2 && signalBJets[0].Pt()<175 && fabs(signalBJets[1].Eta())<1.2 && signalBJets[0].DeltaPhi(nonBJets[0])>2.2 && signalBJets[1].DeltaPhi(nonBJets[0])>1.6;
  bool SRD = SRD0 || SRD1 || SRD2;

  if ( SRD ) accept("SRD");
  if ( SRD0 ) accept("SRD0");
  if ( SRD1 ) accept("SRD1");
  if ( SRD2 ) accept("SRD2");

  //////////////////////////////
  // Finished with event
  return;
}
