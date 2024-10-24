import os
import sys
import subprocess
import ROOT
import copy

# Input arguments
datacard = sys.argv[1]
operator = sys.argv[2]
region = sys.argv[3]
range_val = sys.argv[4]
year = sys.argv[5]

# Lista di tutti gli operatori
all_operators = ['cT0', 'cT1', 'cT2', 'cT3', 'cT4', 'cT5', 'cT6', 'cT7', 'cT8', 'cT9', 
                 'cS0', 'cS1', 'cS2', 'cM0', 'cM1', 'cM2', 'cM3', 'cM4', 'cM5', 'cM7']

# Funzione per eseguire comandi shell
def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(f"Error executing command: {command}")
        print(stderr.decode("utf-8"))
    else:
        print(stdout.decode("utf-8"))

# 1. Rimozione di file esistenti e creazione della workspace root
run_command("rm -rf model_test.root")
workspace_command = (
    f"text2workspace.py {datacard} "
    "-P HiggsAnalysis.AnalyticAnomalousCoupling.AnomalousCouplingEFTNegative:analiticAnomalousCouplingEFTNegative "
    "-o model_test.root "
    "--X-allow-no-signal "
    "--PO eftOperators=cT0,cT1,cT2,cT3,cT4,cT5,cT6,cT7,cT8,cT9,cS0,cS1,cS2,cM0,cM1,cM2,cM3,cM4,cM5,cM7"
)
run_command(workspace_command)

# 2. Preparazione per il fit con singolo operatore, congelando gli altri
freeze_params = "r"
set_params = "r=1"
for op in all_operators:
    if op != operator:
        freeze_params += f",k_{op}"
        set_params += f",k_{op}=0"

# Fit aspettato
fit_expected_command = (
    f"combine -M MultiDimFit model_test.root "
    f"-m 125 -t -1 --expectSignal=1 "
    f"--redefineSignalPOIs k_{operator} "
    f"--freezeParameters {freeze_params} "
    f"--setParameters {set_params} "
    f"--setParameterRanges k_{operator}=-{range_val},{range_val} "
    f"--verbose -1 -n {operator}_{region}_expected "
    "--algo=grid --points 50 --fastScan"
)
run_command(fit_expected_command)

# Fit osservato
fit_observed_command = (
    f"combine -M MultiDimFit model_test.root "
    f"-m 125 "
    f"--redefineSignalPOIs k_{operator} "
    f"--freezeParameters {freeze_params} "
    f"--setParameters {set_params} "
    f"--setParameterRanges k_{operator}=-{range_val},{range_val} "
    f"--verbose -1 -n {operator}_{region}_observed "
    "--algo=grid --points 50 --fastScan"
)
run_command(fit_observed_command)

# 3. Funzione di post-processing del grafico ROOT
def process_graph(graph):
    x_std = []
    x_y_map = []
    x_value = ROOT.Double()
    y_value = ROOT.Double()

    ip = 0
    while ip < graph.GetN():
        graph.GetPoint(ip, x_value, y_value)

        if x_value in x_std:
            graph.RemovePoint(ip)
            ip -= 1
        else:
            x_std.append(copy.deepcopy(x_value))
            x_y_map.append([copy.deepcopy(x_value), copy.deepcopy(y_value)])

        ip += 1

    graph.Set(0)
    
    if len(x_y_map) > 0:
        min_x = -100.
        minimum = 1000.

        for it in x_y_map:
            if it[1] < minimum:
                minimum = it[1]
                min_x = it[0]

        for it in x_y_map:
            it[1] = it[1] - minimum
  
        ip = 0
        for it in x_y_map:
            graph.SetPoint(ip, it[0], it[1])
            ip += 1

    return graph, min_x

# 4. Creazione e visualizzazione dei grafici
def draw_graph(expected_file, observed_file, operator, year, region):
    ROOT.gROOT.SetBatch()
    cc = ROOT.TCanvas("cc","", 800, 600)

    # Apri i file ROOT
    _file1 = ROOT.TFile.Open(expected_file, "READ") 
    _file2 = ROOT.TFile.Open(observed_file, "READ")

    # Ottieni il limite dai file
    limit = _file1.Get("limit")
    limitData = _file2.Get("limit")

    # Crea i grafici
    toDraw = ROOT.TString(f"2*deltaNLL:{operator}")
    graphScan = ROOT.TGraph(limit.Draw(toDraw.Data(), "deltaNLL<50 && deltaNLL>-30", "l"), limit.GetV2(), limit.GetV1())
    graphScanData = ROOT.TGraph(limitData.Draw(toDraw.Data(), "deltaNLL<50 && deltaNLL>-30", "l"), limitData.GetV2(), limitData.GetV1())

    graphScan.RemovePoint(0)
    graphScanData.RemovePoint(0)

    graphScan, mc_min_x = process_graph(graphScan)
    graphScanData, data_min_x = process_graph(graphScanData)

    # Stile grafico
    graphScan.SetMarkerStyle(21)
    graphScan.SetLineWidth(2)
    graphScan.SetMarkerColor(ROOT.kBlue)
    graphScan.SetLineColor(ROOT.kBlue)

    graphScanData.SetMarkerStyle(21)
    graphScanData.SetLineWidth(2)
    graphScanData.SetMarkerColor(ROOT.kRed)
    graphScanData.SetLineColor(ROOT.kRed)

    cc.SetGrid()
    graphScan.Draw("al")
    graphScanData.Draw("l same")

    # Salva il grafico come immagine
    cc.SaveAs(f"LS_{operator}.png")

    return mc_min_x, data_min_x

# 5. Richiamo della funzione per creare il grafico
expected_file = f"higgsCombine{operator}_{region}_expected.MultiDimFit.mH125.root"
observed_file = f"higgsCombine{operator}_{region}_observed.MultiDimFit.mH125.root"
mc_min_x, data_min_x = draw_graph(expected_file, observed_file, operator, year, region)

print(f" (expected) MC at minimum: {mc_min_x}")
print(f" (observed) data at minimum: {data_min_x}")

# 6. Scrittura dei risultati in un file di output
def save_confidence_intervals(filename, operator, year, region, lower, upper):
    with open(filename, 'a') as f:
        f.write(f"{operator} {year} {region} {lower} {upper}\n")

# Salva i risultati
save_confidence_intervals('yearCI_exp-pLHE_22October2024.txt', operator, year, region, mc_min_x, data_min_x)
save_confidence_intervals('yearCI_obs-pLHE_22October2024.txt', operator, year, region, mc_min_x, data_min_x)
