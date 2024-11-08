#!/bin/bash
# combine model from Massiro: https://github.com/UniMiBAnalyses/D6EFTStudies , https://github.com/amassiro/AnalyticAnomalousCoupling 

    ### launch it like: 
    ### sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/YearsCombination_8June2022/combined_boosted_bVeto.txt cT0 boosted_bVeto 

datacard=$1
operator=$2
region=$3
range=$4
year=$5

#FIT_OPTIONS="--robustFit=1 --setRobustFitTolerance=0.2 --cminDefaultMinimizerStrategy=0 \
#--X-rtd=MINIMIZER_analytic --X-rtd MINIMIZER_MaxCalls=99999999999 --cminFallbackAlgo Minuit2,Migrad,0:0.2 \
#--stepSize=0.005 --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND
#"
## easy fit? decomment here:
#FIT_OPTIONS="--cminDefaultMinimizerStrategy=0 --robustFit=1 --fastScan "


#rm -rf model_test.root

    #################################################################
    #### STEP 1: MAKE THE WORKSPACE WITH THE A.C.
    ### when the datacard is produced with ALL possibile WC turned on, the workspace can be produced specifying all operators --PO=cT0, etc etc
    ### and then freeze all the others to 0
    #################################################################
 
    ###### uncomment for 1D limits
    # create rootfit workspace from datacard: case of 1D limits 
text2workspace.py  ${datacard} \
   -P HiggsAnalysis.AnalyticAnomalousCoupling.AnomalousCouplingEFTNegative:analiticAnomalousCouplingEFTNegative \
   -o model_test.root \
   --PO reuseCompleteDatacards \
   --PO eftOperators=cT0,cT1,cT2,cT3,cT4,cT5,cT6,cT7,cT8,cT9,cS0,cS1,cS2,cM0,cM1,cM2,cM3,cM4,cM5,cM7
   #--PO eftOperators=${operator}  ## this is for cards with ONLY ONE OPERATOR 
   #--PO  addDim8 \

    ###### uncomment for 2D limits
    # create rootfit workspace from datacard: case of 2D limits 
#text2workspace.py  ${datacard} \
#   -P HiggsAnalysis.AnalyticAnomalousCoupling.AnomalousCouplingEFTNegative:analiticAnomalousCouplingEFTNegative \
#   -o model_test.root \
#   --PO reuseCompleteDatacards \
#   --X-allow-no-signal \
#   --PO eftOperators=cT0,cT1,cT2,cT3,cT4,cT5,cT6,cT7,cT8,cT9,cS0,cS1,cS2,cM0,cM1,cM2,cM3,cM4,cM5,cM7

    ###### uncomment for all operators measured simultaneously
    # create rootfit workspace from datacard: case of n-dim limits


   ### when the datacard is produced with ALL possibile WC turned on, the workspace can be produced specifying all operators --PO=cT0, etc etc
   ### and then freeze all the others to 0


   #################################################################
   #       STEP 2: RUN EXPECTED LIMITS                             #
   #       run  for single operator, fitting options improved:     #
   #                       expected                                #
   #################################################################
rm -rf higgs*root
   #1. fit 
   # expected
   # it's better to keep the option --setParameters r=1 for both expected and observed according to Giacomo
   # when fitting on one operator, freeze all the others if the datacards contain them all
# Lista di tutti gli operatori possibili
all_operators=(cT0 cT1 cT2 cT3 cT4 cT5 cT6 cT7 cT8 cT9 cS0 cS1 cS2 cM0 cM1 cM2 cM3 cM4 cM5 cM7)
# Crea una stringa con tutti gli operatori tranne quello selezionato
freeze_params="r"
set_params="r=1"
for op in "${all_operators[@]}"; do
    if [[ $op != $operator ]]; then
        freeze_params="${freeze_params},k_${op}"
        set_params="${set_params},k_${op}=0"
    fi
done


combine -M MultiDimFit model_test.root \
   -m 125 -t -1 \
   --redefineSignalPOIs k_${operator} \
   --freezeParameters ${freeze_params} \
   --setParameters ${set_params} \
   --setParameterRanges k_${operator}=-${range},${range} \
   -v -3 \
   -n ${2}_${3}_expected \
   --algo=grid --points 120 \
   --cminDefaultMinimizerStrategy=0 --robustFit=1 \
   --fastScan 
#   --expectSignal=1 \
   #--robustFit=1 --setRobustFitTolerance=0.2 \
   #--X-rtd MINIMIZER_MaxCalls=99999999999 --cminFallbackAlgo Minuit2,Migrad,0:0.2 \
   #--stepSize=0.005     --X-rtd FITTER_NEW_CROSSING_ALGO \
   #--X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND \


#   # observed
combine -M MultiDimFit model_test.root \
   -m 125 \
   --redefineSignalPOIs k_${operator} \
   --freezeParameters ${freeze_params} \
   --setParameters ${set_params} \
   --setParameterRanges k_${operator}=-${range},${range} \
   -v -3 \
   -n ${2}_${3}_observed \
   --algo=grid --points 120 \
   --cminDefaultMinimizerStrategy=0 --robustFit=1 \
   --fastScan 
   #--robustFit=1 --setRobustFitTolerance=0.2 \
   #--cminDefaultMinimizerStrategy=0 --X-rtd=MINIMIZER_analytic \
   #--X-rtd MINIMIZER_MaxCalls=99999999999 --cminFallbackAlgo Minuit2,Migrad,0:0.2 \
   #--stepSize=0.005     --X-rtd FITTER_NEW_CROSSING_ALGO \
   #--X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND \
   #--algo=grid --points 200 --robustFit=1 --cminDefaultMinimizerStrategy=0 \
#
#   #--fastScan #\
#   #--setRobustFitTolerance=0.1 \
#   #--cminDefaultMinimizerTolerance 0.1 \
#   #--X-rtd=MINIMIZER_analytic --X-rtd MINIMIZER_MaxCalls=99999999999999 \
#   #--cminFallbackAlgo Minuit2,Migrad,0:1 --stepSize=0.1 --setRobustFitStrategy=1 \
#   #--maxFailedSteps 999999 --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP \
#   #--X-rtd FITTER_BOUND
#
#
#    ##2a. plot the profile likelihood obtained: do this with python plotter (only expected)
##python drawLS.py \
##        higgsCombine${2}_${3}_expected.MultiDimFit.mH125.root k_${operator} ${year} ${region}
#
#    ##2b. plot the profile likelihood obtained: do this with python plotter (expected+observed)

python3 /work/mpresill/combinev10/CMSSW_14_1_0_pre4/src/CombineUtils/EFT/VBS_ZVjj_dim8/drawLS_wData.py \
        higgsCombine${2}_${3}_expected.MultiDimFit.mH125.root \
        k_${operator} ${year} ${region} \
        higgsCombine${2}_${3}_observed.MultiDimFit.mH125.root 
#        
    ##3. backup the plot to webpage
#mkdir -p /eos/user/m/mpresill/www/VBS/EFTlimits_ZVjj+WVjj/
#cp /eos/user/m/mpresill/www/VBS/EFTlimits/index.php /eos/user/m/mpresill/www/VBS/EFTlimits/.
cp  LS_k_${operator}.png /web/mpresill/public_html/VBS_semilep/EFTlimits/ZVjj_${operator}_${region}_${year}_pLHE_Giacomo_22Oct2024_v2.png
#
    #######################################
    #     run  for two operators a time:  #
    ####################################### 

