#!/bin/bash

tag=cms_vbshad_2021_2_DNN_comb_all      #### Ã¨ un tag per il tuo output e le cartelle varie che vai a creare
datacardNAME=/ceph/mpresill/VBS_hadronic/MARCH21/cms_vbshad_2021_2_DNN_comb_all                       #### Ã¨ il path per la tua datacard (senza .txt)

cd tmp
rm -rf *   
#   copy your workspace as "datacard.root" in the tmp directory
cp PATH_TO_YOUR_WORKSPACE datacard.root


python $CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/systematicsAnalyzer.py ${datacardNAME}.txt --all -f html > systenaticsAnalyzer_${tag}.html
xrdcp -f systenaticsAnalyzer_${tag}.html root://eosuser.cern.ch//eos/user/m/mpresill/www/VBS_hadronic/NuisancesReport/.         ### backup in una cartella eos

echo "following workspace was used: "${tag}.root
#################################################################################################################################################
#combine -M Significance datacard.root   --cminDefaultMinimizerStrategy 0 --cminFallbackAlgo Minuit2,Migrad,0:0.2 -v 2 &> significance_${tag}_observed.txt
combine -M Significance datacard.root -t -1 --expectSignal=1  --cminDefaultMinimizerStrategy 0 --cminFallbackAlgo Minuit2,Migrad,0:0.2 -v 2 &> significance_${tag}_expected.txt
combine -M Significance datacard.root -t -1 --expectSignal=1 --toysFreq --cminDefaultMinimizerStrategy 0 --cminFallbackAlgo Minuit2,Migrad,0:0.2 -v 2 &> significance_${tag}_expected_toysFreq.txt
xrdcp -rf significance_*.txt root://eosuser.cern.ch//eos/user/m/mpresill/www/VBS_hadronic/significance/.                        ### backup in una cartella eos

mkdir -p ../fit/${tag}

combine -M FitDiagnostics datacard.root \
        --out ../fit/${tag} \
        --rMin -10 --rMax 10 \
        --saveNormalizations --saveWithUncertainties \
        --robustFit=1 --cminDefaultMinimizerStrategy 0 -t -1 \
        --setParameterRanges 'rgx{.*norm_.*}'=-2,4              # I suggest this option as bounds the rateParameters to avoid strange things
        #--cminFallbackAlgo Minuit2,Migrad,0:0.2  --setRobustFitTolerance 0.2 --stepSize=0.001 
        #--autoBoundsPOIs r
python $CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/diffNuisances.py --all --abs --format html ../fit/${tag}/fitDiagnosticsTest.root > fit_${tag}.html
xrdcp -rf  fit_${tag}.html root://eosuser.cern.ch//eos/user/m/mpresill/www/VBS_hadronic/diffNuisances/.                         ### backup in una cartella eos

python $CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/mlfitNormsToText.py ../fit/${tag}/fitDiagnosticsTest.root > postfit_${tag}_norm.txt
xrdcp -rf  postfit_${tag}_norm.txt root://eosuser.cern.ch//eos/user/m/mpresill/www/VBS_hadronic/diffNuisances/.                 ### backup in una cartella eos
        
        # fast scan     (if you wish, it makes the scanes on single nuisances to check the LL)
#combineTool.py -M FastScan -w datacard.root:w 
#cp nll.pdf /eos/user/m/mpresill/www/VBS_hadronic/diffNuisances/FastScan_Run2${tag}.pdf

        ###############
echo "FitDiagnostic file : "../fit/${tag}/fitDiagnosticsTest.root 
echo "following workspace was used: "/ceph/mpresill/VBS_hadronic/MARCH21/workspace_2021_DNN_comb_all_VVEWK.root 
