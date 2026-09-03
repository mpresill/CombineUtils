#!/bin/bash

######### YOU NEED ONE INPUT: datacard.root, which is your workspace. Be careful: this code uses unblind data as default option.

Date=$(date +%F)
tag=NAME


options1="--cminFallbackAlgo Minuit2,Migrad,0:1  --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND --X-rtd=MINIMIZER_analytic --X-rtd MINIMIZER_MaxCalls=9999999"

options3="--robustFit=1 --cminDefaultMinimizerStrategy 0 --X-rtd MINIMIZER_MaxCalls=9999999 --cminFallbackAlgo Minuit2,Migrad,0:0.2  --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND --setRobustFitTolerance 0.2 --stepSize=0.001"

options4="--robustFit=1 --cminDefaultMinimizerStrategy 2 --X-rtd MINIMIZER_MaxCalls=9999999 --cminFallbackAlgo Minuit2,Migrad,0:0.2  --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND --setRobustFitTolerance 0.2 --stepSize=0.001"

options5="--robustFit=1 --cminDefaultMinimizerStrategy 0" 

options6=""

ranges="--setParameterRanges "
rateParamsRanges="'rgx{norm_.*}=0,5'" 

blindOrnot="-t -1 --toysFrequentist --expectSignal 1 "


mkdir tmp 
cd tmp
rm -rf *


inputCard=../datacard

outputFolder=../Impacts_${Date}_${tag}

mkdir -p ${outputFolder}

combineTool.py -M Impacts -d ${inputCard}.root ${blindOrnot} --rMin -10 --doInitialFit -m 1 -n ${tag} --parallel 30  ${options5} ${ranges}${rateParamsRanges} 

combineTool.py -M Impacts -d ${inputCard}.root ${blindOrnot} --rMin -10 --doFits -m 1 -n ${tag} --parallel 30 ${options5} ${ranges}${rateParamsRanges} 

combineTool.py -M Impacts -d ${inputCard}.root -m 1 -n ${tag} -o ${outputFolder}/impacts_${tag}.json --parallel 30

plotImpacts.py -i  ${outputFolder}/impacts_${tag}.json -o  ${outputFolder}/impacts_${tag}_${Date} --summary

cd ..

