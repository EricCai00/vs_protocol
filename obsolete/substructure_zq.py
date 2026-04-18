# 导入依赖包
from rdkit.Chem import AllChem as ch
from rdkit.Chem import Draw as d

# 载入substructure结构
substructure_smiles = ['CNC1=NC=CC=N1', 'C12=NC=NC=C1C=CC=C2', 'C12=CC=CC=C1C=CC=N2', 'C1(NC=C2)=C2C=NC=N1', 'CNC1=NC=CC=C1', 'O=C(N1)CC2=C1C=CC=C2', 'C12=NC=NC=C1N=CN2']

# 使用SD文件中的分子进行匹配
suppl = ch.SDMolSupplier('/public/home/zhangqian/withdrawn_safe/PLK1_substructure/taoshu2.sdf')
mols = [x for x in suppl if x is not None]
print(len(mols)) #获取分子数目

# 对每个子结构分别进行搜索并保存匹配的结构
for idx, smiles in enumerate(substructure_smiles):
    # 将SMILES转化为Mol对象
    pattern = ch.MolFromSmiles(smiles)
    if pattern is not None:
        print(f"子结构 {idx+1} 创建成功！")
        # 匹配包含当前子结构的分子
        matching_molecules = []
        for mol in mols:
            if mol.HasSubstructMatch(pattern):
                matching_molecules.append(mol)

        print(f"匹配子结构 {idx+1} 的分子数:", len(matching_molecules))

        # 保存匹配的结构到SD文件
        w = ch.SDWriter(f'matched_structures_substructure_{idx+1}.sdf')
        for mol in matching_molecules:
            w.write(mol)
        w.close()
    else:
        print(f"子结构 {idx+1} 创建失败！")
