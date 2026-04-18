import sys
import shutil

path = sys.argv[2]


def make_complex():
    with open(f'{path}/{sys.argv[3]}') as f:
        lines = f.readlines()

    with open(f'{path}/ligand.gro') as f:
        ligand_lines = f.readlines()

    for line in ligand_lines:
        if line.strip().startswith('1MOL'):
            lines.insert(-1, line)

    num = int(lines[1].strip()) + int(ligand_lines[1].strip())
    lines[1] = f'{num:5}\n'

    with open(f'{path}/complex.gro', 'w') as f:
        f.writelines(lines)


def process_topol_1():
    with open(f'{path}/topol.top') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line == '[ moleculetype ]\n':
            break

    with open(f'{path}/ligand.itp') as f:
        ligand_lines = f.readlines()

    start = False
    new_ligand_lines = []
    for line in ligand_lines:
        if line.startswith('['):
            start = False

        if start:
            lines.insert(i, line)
            i += 1

        elif line == '[ atomtypes ]\n':
            start = True
            lines.insert(i, line)
            i += 1
        else:
            new_ligand_lines.append(line)

    i = 0
    for char in lines[-1]:
        if char != '\n':
            i += 1
    lines.insert(len(lines), 'ligand' + ' ' * (i - 7) + '1\n')

    for i, line in enumerate(lines):
        if line == '; Include water topology\n':
            break

    lines.insert(i, '; Include ligand topology\n')
    lines.insert(i + 1, '#include "ligand.itp"\n')
    lines.insert(i + 2, '\n')

    with open(f'{path}/topol_1.top', 'w') as f:
        f.writelines(lines)

    shutil.move(f'{path}/topol.top', f'{path}/topol_ori.top')
    shutil.move(f'{path}/topol_1.top', f'{path}/topol.top')


    with open(f'{path}/ligand_1.itp', 'w') as f:
        f.writelines(new_ligand_lines)

    shutil.move(f'{path}/ligand.itp', f'{path}/ligand_ori.itp')
    shutil.move(f'{path}/ligand_1.itp', f'{path}/ligand.itp')


def process_topol_2():
    with open(f'{path}/topol.top') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line == '; Include water topology\n':
            break
    
    lines.insert(i, '; Ligand position restraints\n')
    lines.insert(i + 1, '#ifdef POSRES_LIG\n')
    lines.insert(i + 2, '#include "posre_ligand.itp"\n')
    lines.insert(i + 3, '#endif\n')
    lines.insert(i + 4, '\n')

    with open(f'{path}/topol_1.top', 'w') as f:
        f.writelines(lines)
        
    shutil.move(f'{path}/topol.top', f'{path}/topol_ori_1.top')
    shutil.move(f'{path}/topol_1.top', f'{path}/topol.top')


if sys.argv[1] == '1':
    make_complex()
    process_topol_1()

elif sys.argv[1] == '2':
    process_topol_2()
