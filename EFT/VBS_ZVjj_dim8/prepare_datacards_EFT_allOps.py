import os
import shutil
import subprocess


# List of sample names
#samples = ['cT3'] #, 'cT4', 'cT5', 'cT6', 'cT7', 'cT8', 'cT9', 'cS0','cS1','cS2','cM0','cM1','cM2','cM3','cM4','cM5','cM7']
#'cT0', 'cT1', 'cT2', 
# Directory to cd into before running the command
chosen_directory = "/afs/cern.ch/work/m/mpresill/Latino/CMSSW_10_6_4/src/PlotsConfigurations/Configurations/VBS_ZV/2017-v1/boosted-dim8"
#tag_datacards = "6Dec2023_2017-dim8_boosted_wBkg_allOperators"
tag_datacards = "16May2024_2017-dim8-private"


# Input file and output directory
#input_file = "/eos/user/m/mpresill/CMS/VBS/VBS_ZV/histograms/rootFile_6Dec2023_2017-dim8/plots_VBS_ZV_6Dec2023_2017-dim8_boosted_wBkg_allOperators.root"
input_file = "/eos/user/m/mpresill/CMS/VBS/VBS_ZV/histograms/rootFile_16May2024_2017-dim8-private/plots_VBS_ZV_16May2024_2017-dim8-private_boosted_wBkg.root"
output_directory_base = "/eos/user/m/mpresill/CMS/VBS/VBS_ZV/DatacardsEFT/Datacards_" + tag_datacards

# Change directory
os.chdir(chosen_directory)

#for sample in samples:


# Prepare mkDatacards.py command
output_directory = output_directory_base
# Define the command as a list of arguments
command = [
    "mkDatacards.py",
    "--pycfg=" + os.path.abspath('configuration.py'),
    "--samplesFile=" + os.path.abspath('samples-datacards-dim8-allOps.py'),
    "--structureFile=" + os.path.abspath('structure-dim8.py'),
    "--inputFile=" + input_file,
    "--outputDirDatacard=" + output_directory,
    "--skipMissingNuisance",
    "--nuisancesFile=" + os.path.abspath('../nuisances_datacards-dim8.py')
]

####    for TOP CR I have different wat 
commandtopcr = [
    "mkDatacards.py",
    "--pycfg=" + os.path.abspath('configuration.py'),
    "--samplesFile=" + os.path.abspath('samples-datacards-dim8-allOps.py'),
    "--structureFile=" + os.path.abspath('structure-dim8.py'),
    "--inputFile=" + input_file,
    "--outputDirDatacard=" + output_directory,
    "--skipMissingNuisance",
    "--cutsFile=cuts_boosted_topcr.py",
    "--cutsFile=" + os.path.abspath('../boosted/cuts_boosted_topcr.py'),
    "--nuisancesFile=" + os.path.abspath('../nuisances_datacards_topcr.py')
]

# Execute the command
subprocess.call(command)
subprocess.call(commandtopcr)


######## combine the datacards of the single year:







#######



######## for debugging:
# Print the path where the command is executed
#print("Executing command in directory: " + os.getcwd())
# Print the command
#print(command)

