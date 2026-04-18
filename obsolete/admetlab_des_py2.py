#!/public/home/caiyi/software/miniconda3/envs/python2/bin/python

'''
env:
pychem 1.0
numpy 1.16.6
matplotlib 2.2.5
h5py 2.10.0
pandas 0.16.0
scikit-learn 0.17.1
joblib 0.10.0 (copied to sklearn/externals)
rdkit 2018.09.3
'''

from tqdm import tqdm
import math
from multiprocessing import Pool
import pandas as pd
import json
import numpy
import argparse
from rdkit import Chem
from rdkit.Chem import Descriptors
import collections

from pychem import (basak, bcut, charge, connectivity, constitution,
    estate, kappa, moe, molproperty, moreaubroto, topology)
from pychem.moran import _CalculateMoranAutocorrelation


usage = ('admetlab_des.py --input <smi_file> --output <csv_file> --threads 20\n\n'
'Example: admetlab_des.py -i /public/home/caiyi/data/docking/DeepDocking/projects/test_fp/iteration_1/smile/admetlab_test.smi -t 20')

parser = argparse.ArgumentParser(usage=usage)
parser.add_argument('-i', '--input', required=True)
parser.add_argument('-o', '--output', required=True)
parser.add_argument('-t', '--threads', default=1, type=int)
args = parser.parse_args()


d = {}
l = []

# basak
d['CIC0'] = basak.CalculateBasakCIC0
d['CIC2'] = basak.CalculateBasakCIC2
d['CIC3'] = basak.CalculateBasakCIC3
d['CIC6'] = basak.CalculateBasakCIC6
d['IC0'] = basak.CalculateBasakIC0
d['IC1'] = basak.CalculateBasakIC1
d['SIC1'] = basak.CalculateBasakSIC1

# constitution
constitution_list = ['AWeight', 'PC6', 'Weight', 'naccr', 'naro', 'ncarb', 'ndb', 'ndonr', 'nhet', 'nhev', 'nnitro', 'nphos', 'nring', 'nsb', 'nsulph', 'nta']
for label in constitution_list:
    d[label] = constitution._constitutional[label]

# molproperty
d['Hy'] = molproperty.CalculateHydrophilicityFactor
d['LogP'] = molproperty.CalculateMolLogP
d['LogP2'] = molproperty.CalculateMolLogP2
d['TPSA'] = molproperty.CalculateTPSA
d['UI'] = molproperty.CalculateUnsaturationIndex

# connectivity
connectivity_list = ['Chi10', 'Chi4c', 'Chiv1', 'Chiv3', 'Chiv3c', 'Chiv4', 'Chiv4c', 'Chiv4pc', 'Chiv9', 'dchi0', 'dchi3', 'knotp']
for label in connectivity_list:
    d[label] = connectivity._connectivity[label]

# moran

def CalculateMoranAutoMass(mol):
    res = {}
    for i in range(6):
        res["MATSm" + str(i + 1)] = _CalculateMoranAutocorrelation(
            mol, lag=i + 1, propertylabel="m"
        )
    return res

def CalculateMoranAutoVolume(mol):
    res = {}
    for i in range(7):
        res["MATSv" + str(i + 1)] = _CalculateMoranAutocorrelation(
            mol, lag=i + 1, propertylabel="V"
        )
    return res

def CalculateMoranAutoElectronegativity(mol):
    res = {}
    for i in range(6):
        res["MATSe" + str(i + 1)] = _CalculateMoranAutocorrelation(
            mol, lag=i + 1, propertylabel="En"
        )
    return res

def CalculateMoranAutoPolarizability(mol):
    res = {}
    for i in range(6):
        res["MATSp" + str(i + 1)] = _CalculateMoranAutocorrelation(
            mol, lag=i + 1, propertylabel="alapha"
        )
    return res

l.extend([CalculateMoranAutoMass, CalculateMoranAutoVolume, CalculateMoranAutoElectronegativity, CalculateMoranAutoPolarizability])

# kappa
d['kappa2'] = kappa.CalculateKappa2
d['kappa3'] = kappa.CalculateKappa3
d['kappam3'] = kappa.CalculateKappaAlapha3
d['phi'] = kappa.CalculateFlexibility

# bcut
l.extend([bcut.CalculateBurdenElectronegativity, bcut.CalculateBurdenMass, bcut.CalculateBurdenPolarizability, bcut.CalculateBurdenVDW])

# topology
topology_list = ['AW', 'Arto', 'BertzCT', 'GMTIV', 'Geto', 'Getov', 'Gravto', 'Hatov', 'IDE', 'IDET', 'J', 'MZM1', 'MZM2', 'TIAC']

def CalculateGutmanVTopo(mol):
    nAT = mol.GetNumAtoms()
    deltas = topology._HKDeltas(mol)
    Distance = Chem.GetDistanceMatrix(mol)
    res=0.0
    try:
        for i in range(nAT):
            for j in range(i+1,nAT):
                res = res + deltas[i] * deltas[j] * Distance[i, j]
    except:
        print('---------------------')
        print(i, j, len(deltas), Distance.shape)
        print(Chem.MolToSmiles(mol))

    return numpy.log10(res)

topology_dict = topology._Topology
topology_dict['GMTIV'] = CalculateGutmanVTopo
for label in topology_list:
    d[label] = topology_dict[label]
    # d[label] = topology._Topology[label]

# charge
charge_list = ['LDI', 'Mnc', 'QCmax', 'QCss', 'QHmax', 'QHss', 'QNmax', 'QNmin', 'QNss', 'QOmax', 'QOmin', 'QOss', 'Qass', 'Qmax', 'Qmin', 'Rnc', 'Rpc', 'SPP', 'Tnc', 'Tpc']
for label in charge_list:
    d[label] = charge._Charge[label]

# moreaubroto
def CalculateMoreauBrotoAutoMass(mol):
    res = {}

    for i in range(6):
        res["ATSm" + str(i + 1)] = moreaubroto._CalculateMoreauBrotoAutocorrelation(
            mol, lag=i + 1, propertylabel="m"
        )

    return res

l.append(CalculateMoreauBrotoAutoMass)

# moe
l.extend([moe.CalculateEstateVSA, moe.CalculateSMRVSA, moe.CalculatePEOEVSA, moe.CalculateVSAEstate, moe.CalculateSLOGPVSA])

# estate
def GetAtomLabel45(mol):
    smart = "[PD4H0](=*)(-*)(-*)-*"
    patt = Chem.MolFromSmarts(smart)
    matches = mol.GetSubstructMatches(patt, uniquify=0)
    cc = []
    for match in matches:
        cc.append(match[0])
    bb = list(numpy.unique(numpy.array(cc)))
    return bb

def CalculateMinAtomType45EState(mol):
    AT = GetAtomLabel45(mol)
    Estate = estate._CalculateEState(mol)
    if AT == []:
        res = 0
    else:
        res = min([Estate[k] for k in AT])
    return round(res, 3)

def CalculateMaxAtomType45EState(mol):
    AT = GetAtomLabel45(mol)
    Estate = estate._CalculateEState(mol)
    if AT == []:
        res = 0
    else:
        res = max([Estate[k] for k in AT])
    return round(res, 3)

l.extend([estate.CalculateEstateValue])
d['DS'] = estate.CalculateDiffMaxMinEState
d['Smin'] = estate.CalculateMinEState
d['Smin45'] = CalculateMinAtomType45EState
d['Smax45'] = CalculateMaxAtomType45EState

# additional
d['MW'] = Descriptors.ExactMolWt
d['MR'] = molproperty.CalculateMolMR
d['nRotbond'] = constitution.CalculateRotationBondNumber
d['nrigidbond'] = lambda mol: mol.GetNumBonds() - constitution.CalculateRotationBondNumber(mol)


# calculate all
with open('/public/home/caiyi/github/admet/ADMETlab/admetlab_labels.json', 'r') as f:
    label_dict = json.load(f)

all_labels = []
for task, labels in label_dict.items():
    all_labels.extend(labels)
all_labels.extend(['MW', 'MR', 'nRotbond', 'nrigidbond'])
all_labels = set(all_labels)

def admetlab_descriptors(smi):
    mol = Chem.MolFromSmiles(smi)
    des = {}
    # print('askjdhaxcgidasbi')
    for label, func in d.items():
        # print('askjdhaxcgidasbi', label, func)
        des[label] = func(mol)
    for func in l:
        des.update(func(mol))
    for label in list(des.keys()):
        if label not in all_labels:
            del des[label]
    return des

def calculate_split(lines):
    # smi2des = collections.OrderedDict()
    name2des = collections.OrderedDict()
    for line in tqdm(lines):
        smi, name = line.split()
        try:
            # print(smi, name)
            # smi2des[smi] = admetlab_descriptors(smi)
            name2des[name] = admetlab_descriptors(smi)
            # print(name2des[name])
        except:
            name2des[name] = {}
            print('Error on: ' + smi + ' ' + name + '\n')
            with open('err.txt', 'a') as f:
                f.write(smi + ' ' + name + '\n')

    # return smi2des
    return name2des

with open(args.input) as f:
    lines = f.read().splitlines()
split_len = int(math.ceil(float(len(lines)) / args.threads))
line_splits = [lines[int(i * split_len): int((i+1) * split_len)] for i in range(args.threads)]

pool = Pool(args.threads)
out_list = pool.map(calculate_split, line_splits)
# If stuck here, there is '.' in your smi file
pool.close()

df_list = [pd.DataFrame(name2des).T for name2des in out_list]
# df_list = pd.DataFrame(calculate_split(lines)).T

df = pd.concat(df_list)
# df.index.name = 'smiles'
df.index.name = 'name'
df.to_csv(args.output)
