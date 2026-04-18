import argparse

if __name__ == '__main__':
    # import sys
    # sys.path.append('/public/home/caiyi/eric_github/vs_protocol/')
    # print(sys.path)
    from deduplicate import deduplicate
    from admetlab_descriptors import admetlab_descriptors
    # from generate_fp import batch_generate_fp
else:
    pass

import sys
import warnings
from collections import namedtuple

import numpy

# from rdkit import DataStructs, ForceField, RDConfig, rdBase
# from rdkit.Chem import *
# from rdkit.Chem.ChemicalFeatures import *
# from rdkit.Chem.EnumerateStereoisomers import (EnumerateStereoisomers,
#                                                StereoEnumerationOptions)
# from rdkit.Chem.rdChemReactions import *
# from rdkit.Chem.rdDepictor import *
# from rdkit.Chem.rdDistGeom import *
# from rdkit.Chem.rdFingerprintGenerator import *
# from rdkit.Chem.rdForceFieldHelpers import *
# from rdkit.Chem.rdMolAlign import *
# from rdkit.Chem.rdMolDescriptors import *
# from rdkit.Chem.rdMolEnumerator import *
from rdkit.Chem.rdMolTransforms import *
# from rdkit.Chem.rdPartialCharges import *
# from rdkit.Chem.rdqueries import *
# from rdkit.Chem.rdReducedGraphs import *
# from rdkit.Chem.rdShapeHelpers import *
# from rdkit.Geometry import rdGeometry
# from rdkit.RDLogger import logger

try:
  from rdkit.Chem.rdSLNParse import *
except ImportError:
  pass

# Mol.Compute2DCoords = Compute2DCoords
# Mol.ComputeGasteigerCharges = ComputeGasteigerCharges


def func(input, wd, suffix, threads):
    admetlab_descriptors(
        input, wd, threads
    # '/public/home/caiyi/data/vs_protocol/strict/module_2/admetlab_input_strict.smi',
    # '/public/home/caiyi/data/vs_protocol/strict/module_2/descriptors.csv',
    # 60

    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-d', '--wd', required=True)
    parser.add_argument('-s', '--suffix', required=True)
    parser.add_argument('-t', '--threads', default=1, type=int)
    args = parser.parse_args()
    func(args.input, args.wd, args.suffix, args.threads)
