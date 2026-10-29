import math
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Draw, Descriptors, rdMolDescriptors, AllChem
import py3Dmol


def smiles_to_mol(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    return mol


def accept_smiles():
    """Keep asking for SMILES until the user just presses Enter."""
    smiles_list = []
    while True:
        s = input("Enter SMILES (press Enter to finish): ").strip()
        if not s:
            break
        smiles_list.append(s)
    return smiles_list


def build_mols(smiles_list):
    """Convert SMILES to mols, skip (and report) the invalid ones."""
    mols, good_smiles = [], []
    for s in smiles_list:
        try:
            mols.append(smiles_to_mol(s))
            good_smiles.append(s)
        except ValueError as e:
            print(e)
    return mols, good_smiles


def print_canonical(smiles_list):
    for s in smiles_list:
        print(s, "-> canonical:", Chem.MolToSmiles(smiles_to_mol(s)))


def draw_grid(mols, smiles_list, per_row=4):
    """2D picture of all the molecules."""
    return Draw.MolsToGridImage(
        mols,
        molsPerRow=per_row,
        subImgSize=(250, 200),
        legends=smiles_list,
    )


def basic_descriptors(smiles):
    m = smiles_to_mol(smiles)
    return {
        "SMILES": smiles,
        "Canonical": Chem.MolToSmiles(m),
        "MW": round(Descriptors.MolWt(m), 2),
        "logP": round(Descriptors.MolLogP(m), 2),
        "HBD": rdMolDescriptors.CalcNumHBD(m),
        "HBA": rdMolDescriptors.CalcNumHBA(m),
        "TPSA": round(rdMolDescriptors.CalcTPSA(m), 2),
    }


def descriptor_table(smiles_list):
    return pd.DataFrame([basic_descriptors(s) for s in smiles_list])


def smiles_to_3d_mol(smiles, seed=42):
    m = Chem.AddHs(smiles_to_mol(smiles))

    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    if AllChem.EmbedMolecule(m, params) != 0:
        raise RuntimeError(f"3D embedding failed for: {smiles}")

    AllChem.UFFOptimizeMolecule(m, maxIters=200)
    return m


def build_3d_mols(smiles_list):
    """Make a 3D model for every SMILES. Failed ones are skipped."""
    mols_3d, ok_smiles = [], []
    for s in smiles_list:
        try:
            mols_3d.append(smiles_to_3d_mol(s))
            ok_smiles.append(s)
        except (ValueError, RuntimeError) as e:
            print(e)
    return mols_3d, ok_smiles


def view_3d_grid(mols_3d, smiles_list, style="stick", per_row=3, cell=(300, 250)):
    """One py3Dmol window with a panel for each 3D molecule."""
    n = len(mols_3d)
    cols = min(n, per_row)
    rows = math.ceil(n / per_row)

    v = py3Dmol.view(
        width=cell[0] * cols,
        height=cell[1] * rows,
        viewergrid=(rows, cols),
        linked=False,
    )
    for i, (m, s) in enumerate(zip(mols_3d, smiles_list)):
        pos = divmod(i, per_row)  # (row, col)
        v.addModel(Chem.MolToMolBlock(m), "mol", viewer=pos)
        v.setStyle({style: {}}, viewer=pos)
        v.addLabel(s, {"fontSize": 12, "backgroundOpacity": 0.4}, viewer=pos)
        v.zoomTo(viewer=pos)
    return v


def in_notebook():
    ip = globals().get("get_ipython")
    if ip is None:
        return False
    try:
        return ip().__class__.__name__ == "ZMQInteractiveShell"
    except Exception:
        return False


def make_models(smiles_list):
    """2D grid + 3D viewer. Shows inline in Jupyter, saves files otherwise."""
    mols, smiles_list = build_mols(smiles_list)
    if not mols:
        print("No valid molecules, nothing to draw.")
        return

    grid_img = draw_grid(mols, smiles_list)
    mols_3d, smiles_3d = build_3d_mols(smiles_list)
    viewer = view_3d_grid(mols_3d, smiles_3d) if mols_3d else None

    if in_notebook():
        from IPython.display import display
        display(grid_img)
        if viewer:
            viewer.show()
    else:
        grid_img.save("molecules_2d.png")
        print("Saved molecules_2d.png")
        if viewer:
            viewer.write_html("molecules_3d.html")
            print("Saved molecules_3d.html (open it in a browser)")


if __name__ == "__main__":
    my_smiles_list = accept_smiles()

    print_canonical(build_mols(my_smiles_list)[1])
    print(descriptor_table(build_mols(my_smiles_list)[1]))
    
    make_models(my_smiles_list)