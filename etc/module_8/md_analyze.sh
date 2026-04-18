#!/usr/bin/bash

# Need to prepare: mmpbsa.in

GMX_MMPBSA=/public/home/caiyi/software/miniconda3/envs/python39/bin/gmx_MMPBSA

printf '1 0\n' | gmx trjconv -s md_0_100.tpr -f traj_comp.xtc -o md_0_100_center.xtc -center -pbc mol -ur compact

printf '4 0\n' | gmx trjconv -s md_0_100.tpr -f md_0_100_center.xtc -o md_0_100_fit.xtc -fit rot+trans

printf '22 & ! a H*\nname 23 complex_Heavy\n13 & ! a H*\nname 24 ligand_Heavy\nq\n' | gmx make_ndx -f em.gro -n index.ndx

printf '23 24\n' | gmx rms -s em.tpr -f md_0_100_center.xtc -n index.ndx -tu ns -o rmsd_lig.xvg

# printf '23 23\n' | gmx rms -s em.tpr -f md_0_100_center.xtc -n index.ndx -tu ns -o rmsd_complex.xvg

printf '1\n' | gmx rmsf -s md_0_100.tpr -f md_0_100_center.xtc -o rmsf_protein.xvg -res

gmx trjconv -f md_0_100_fit.xtc -o trj_80-100ns -b 80000 -e 100000 -dt 200

# conda activate python39
$GMX_MMPBSA -O -i mmpbsa.in -cs md_0_100.tpr -ci index.ndx -cg 1 13 -ct trj_80-100ns.xtc -cp topol.top