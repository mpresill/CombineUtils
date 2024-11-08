
#!/bin/bash


array=(  "cT0" ) #"cT1" "cT2" "cT3" "cT4" "cT5" "cT6" "cT7"  "cT8"  "cT9" ) #"cS0" "cS1"  "cS2" "cM0" "cM1"   "cM2" "cM3" "cM4"   "cM5"  "cM7")  ###here we specify the operators to measure
array2=( "1"   ) #"4"    "4"   "4"   "4"   "4"   "4"   "4"    "4"    "4"  ) #"10"   "10"   "10"  "5"   "10"   "10"   "20"   "10"   "10"   "10" )   ###here we specify the range of the fit
#array=( "cW"  )   ###here we specify the operators to measure
#array2=( "2"  )    ###here we specify the range of the fit




datacards=(
       #"/work/mpresill/datacards/ZVjj_EFT//DatacardsEFT/YearsCombination_22Oct2024-dim8-private-Giacomo_noStatSig/combined_boosted_bVeto.txt"
       #"/work/mpresill/datacards/ZVjj_EFT//DatacardsEFT/YearsCombination_22Oct2024-dim8-private-Giacomo_noStatSig/combined_boosted_bTag.txt"
       "/work/mpresill/datacards/ZVjj_EFT//DatacardsEFT/YearsCombination_22Oct2024-dim8-private-Giacomo_noStatSig/combined_boosted.txt"
)

cd tmp 

for datacard in "${!datacards[@]}"; do
      #rm -rf model_test.root
      #
      #text2workspace.py  ${datacards[datacard]} \
      #      -P HiggsAnalysis.AnalyticAnomalousCoupling.AnomalousCouplingEFTNegative:analiticAnomalousCouplingEFTNegative \
      #      -o model_test.root \
      #      --X-allow-no-signal \
      #      --PO eftOperators=cT0,cT1,cT2,cT3,cT4,cT5,cT6,cT7,cT8,cT9,cS0,cS1,cS2,cM0,cM1,cM2,cM3,cM4,cM5,cM7
      
      for i in "${!array[@]}"; do
            #python scanWC.py /work/mpresill/datacards/ZVjj_EFT/DatacardsEFT/Datacards_22Oct2024_2016-dim8-private-Giacomo/combined_boosted_bVeto.txt     ${array[i]} boosted_bVeto           ${array2[i]}   2016
            #sh eft.sh /work/mpresill/datacards/ZVjj_EFT/DatacardsEFT/Datacards_22Oct2024_2016-dim8-private-Giacomo_noStatSig/combined_boosted_bVeto.txt     ${array[i]} boosted_bVeto           ${array2[i]}   2016
            #sh eft.sh /work/mpresill/datacards/ZVjj_EFT/DatacardsEFT/Datacards_22Oct2024_2016-dim8-private-Giacomo_noStatSig/combined_boosted_bTag.txt      ${array[i]} boosted_bTag            ${array2[i]}   2016
      #      sh eft.sh /work/mpresill/datacards/ZVjj_EFT/DatacardsEFT/Datacards_22Oct2024_2016-dim8-private-Giacomo_noStatSig/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2016
            sh /work/mpresill/combinev10/CMSSW_14_1_0_pre4/src/CombineUtils/EFT/VBS_ZVjj_dim8/eft.sh    ${datacards[datacard]}   ${array[i]} combined_boosted        ${array2[i]}   Run2
      done
done
#
#for i in "${!array[@]}"; do
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_6Dec2023_2017_${array[i]}/combined_boosted_bVeto.txt     ${array[i]} boosted_bVeto           ${array2[i]}   2017
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_6Dec2023_2017_${array[i]}/combined_boosted_bTag.txt      ${array[i]} boosted_bTag            ${array2[i]}   2017
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_6Dec2023_2017_${array[i]}/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2017
#done
#
#for i in "${!array[@]}"; do
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_14May2024_2018-dim8-central/Boosted_SR_bVeto/ZV_mass/datacard.txt     ${array[i]} boosted_bVeto           ${array2[i]}   2018
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_14May2024_2018-dim8-private/Boosted_SR_bVeto/ZV_mass/datacard.txt     ${array[i]} boosted_bVeto           ${array2[i]}   2018
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_14May2024_2018-dim8-central/Boosted_SR_bTag/ZV_mass/datacard.txt      ${array[i]} boosted_bTag            ${array2[i]}   2018
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_14May2024_2018-dim8-private/Boosted_SR_bTag/ZV_mass/datacard.txt      ${array[i]} boosted_bTag            ${array2[i]}   2018
#      #sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_16May2024_2018-dim8-private/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2018
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_16May2024_2018-dim8-private/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2018
#      #sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_6Dec2023_2018-dim8_boosted_wBkg_allOperators/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2018
#      #sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/eft_combination/cards/ZV/2018/ZV_mass/combined_boosted.txt           ${array[i]} combined_boosted        ${array2[i]}   2018
#done
#
#for i in "${!array[@]}"; do
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/YearsCombination_6Dec2023_${array[i]}/combined_boosted_bVeto.txt     ${array[i]} boosted_bVeto           ${array2[i]}   Run2
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/YearsCombination_6Dec2023_${array[i]}/combined_boosted_bTag.txt      ${array[i]} boosted_bTag            ${array2[i]}   Run2
#      sh eft.sh /eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/YearsCombination_6Dec2023_${array[i]}/combined_boosted_ZV_mass.txt           ${array[i]} combined_boosted        ${array2[i]}   Run2
#done


