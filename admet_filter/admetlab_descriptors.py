#!/public/home/caiyi/software/miniconda3/envs/python39/bin/python

from tqdm import tqdm
import math
from multiprocessing import Pool
# import multiprocessing as mp
import pandas as pd
import json
import numpy
import argparse
import collections
import pathlib
# from rdkit.Chem import GraphDescriptors as GD

from PyBioMed.PyMolecule import (basak, bcut, charge, connectivity, constitution,
    estate, kappa, moe, molproperty, moreaubroto, topology)
from PyBioMed.PyMolecule.moran import _CalculateMoranAutocorrelation

from rdkit import RDLogger
lg = RDLogger.logger()
lg.setLevel(RDLogger.ERROR)

script_directory = pathlib.Path(__file__).parent.resolve()
with open(f'{script_directory}/admetlab_labels.json', 'r') as f:
    label_dict = json.load(f)
all_labels = []
for package, labels in label_dict.items():
    all_labels.extend(labels)
all_labels.extend(['MW', 'MR', 'nRotbond', 'nrigidbond', 'StereoCenters', 'SAScore', 'QED'])
all_labels = set(all_labels)

# mp.set_start_method('spawn', force=True)

def calculate_split(lines):
    from rdkit import Chem
    from rdkit.Chem import Descriptors
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
    constitution_list = ['AWeight', 'PC6', 'Weight', 'naccr', 'naro', 'ncarb', 'ndb', 'ndonr', 'nhet', 'nhev', 'nnitro', 'nphos', 
                        #  'nring', 
                        'nsb', 'nsulph', 'nta']
    for label in constitution_list:
        d[label] = constitution._constitutional[label]
    d['nring'] = lambda mol: len(Chem.GetSSSR(mol))

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
    d['MW'] = Descriptors.MolWt
    d['MR'] = molproperty.CalculateMolMR
    d['nRotbond'] = constitution.CalculateRotationBondNumber
    d['nrigidbond'] = lambda mol: mol.GetNumBonds() - constitution.CalculateRotationBondNumber(mol)

    name2des = collections.OrderedDict()
    for line in tqdm(lines):
        smi, name = line.split()
        try:
            mol = Chem.MolFromSmiles(smi)
            des = {}
            for label, func in d.items():
                des[label] = func(mol)
            for func in l:
                des.update(func(mol))
            for label in list(des.keys()):
                if label not in all_labels:
                    del des[label]
            name2des[name] = des
        except:
            name2des[name] = {}
            print('Error on: ' + smi + ' ' + name + '\n')
            with open('err.txt', 'a') as f:
                f.write(smi + ' ' + name + '\n')

    # return smi2des
    return name2des

def admetlab_descriptors(input_, output, threads=1):
    print('input',input_)
    print('output', output)
    print('threads', threads)
    with open(input_) as f:
        lines = f.read().splitlines()
    split_len = math.ceil(len(lines) / threads)
    line_splits = [lines[i * split_len: (i+1) * split_len] for i in range(threads)]

    with Pool(threads) as pool:
        out_list = pool.map(calculate_split, line_splits)
    pool.close()

    # df_list = [pd.DataFrame(smi2des).T for smi2des in out_list]
    df_list = [pd.DataFrame(name2des).T for name2des in out_list]

    df = pd.concat(df_list)
    df.index.name = 'name'
    df.to_csv(output)


if __name__ == '__main__':
    
    usage = ('admetlab_des.py --input <smi_file> --output <csv_file> --threads 20\n\n'
    'Example: admetlab_des.py -i /public/home/caiyi/data/docking/DeepDocking/projects/test_fp/iteration_1/smile/admetlab_test.smi -t 20')

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-t', '--threads', default=1, type=int)
    args = parser.parse_args()

    admetlab_descriptors(args.input, args.output, args.threads)
