from __future__ import annotations

import os
import json
import urllib.parse
import urllib.request
import re
from pathlib import Path

from flask_cors import CORS
from flask import Flask, jsonify, request, send_from_directory
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D


BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000",
    ).split(",")
    if origin.strip()
]
CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


def molecule_svg(molecule: Chem.Mol, background: tuple[float, float, float], dark: bool = False) -> str:
    drawer = rdMolDraw2D.MolDraw2DSVG(300, 220)
    drawer.drawOptions().setBackgroundColour(background)
    drawer.drawOptions().bondLineWidth = 2.5
    draw_molecule = Chem.AddHs(molecule) if molecule.GetNumBonds() == 0 else molecule
    drawer.DrawMolecule(draw_molecule)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    if dark:
        svg = re.sub(r"#0000FF", "#69B7FF", svg, flags=re.IGNORECASE)
        svg = re.sub(r"#000000", "#FFFFFF", svg, flags=re.IGNORECASE)
        svg = re.sub(r"#000(?=[^0-9A-Fa-f]|$)", "#FFFFFF", svg, flags=re.IGNORECASE)
    return svg


KNOWN_NAMES = {
    "C": "Methane",
    "N": "Ammonia",
    "CCO": "Ethanol",
    "CCN": "Ethylamine",
    "c1ccccc1": "Benzene",
    "c1ccncc1": "Pyridine",
    "CC(=O)Oc1ccccc1C(=O)O": "Aspirin",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C": "Caffeine",
    "Cn1c(=O)c2c(ncn2C)n(C)c1=O": "Caffeine",
    "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O": "Glucose",
    "CC(C)Cc1ccc(C(C)C(=O)O)cc1": "Ibuprofen",
    "CC(=O)Nc1ccc(O)cc1": "Acetaminophen",
    "CN1CCCC1c1cccnc1": "Nicotine",
}
name_cache: dict[str, str] = {}
search_cache: dict[str, list[dict[str, str]]] = {}


def molecule_name(smiles: str, canonical: str, supplied_name: str | None = None) -> str:
    if supplied_name and supplied_name.strip():
        name_cache[canonical] = supplied_name.strip()
        return supplied_name.strip()
    if canonical in KNOWN_NAMES:
        return KNOWN_NAMES[canonical]
    if canonical in name_cache:
        return name_cache[canonical]

    candidates = (smiles, canonical)
    for candidate in dict.fromkeys(candidates):
        try:
            query = urllib.parse.quote(candidate, safe="")
            url = (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/"
                f"{query}/property/Title,IUPACName/JSON"
            )
            with urllib.request.urlopen(url, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
            properties = data.get("PropertyTable", {}).get("Properties", [])
            if properties:
                title = properties[0].get("Title") or properties[0].get("IUPACName")
                if title:
                    name = str(title).strip()
                    name_cache[canonical] = name
                    return name
        except Exception:
            continue

    return "Unknown molecule"


def analyze_smiles(smiles: str, supplied_name: str | None = None) -> dict[str, object]:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("Invalid SMILES string")

    canonical = Chem.MolToSmiles(molecule)
    molblock_3d = None
    molecule_3d = Chem.AddHs(molecule)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(molecule_3d, params) == 0:
        AllChem.UFFOptimizeMolecule(molecule_3d, maxIters=200)
        molblock_3d = Chem.MolToMolBlock(molecule_3d)

    return {
        "name": molecule_name(smiles, canonical, supplied_name),
        "smiles": smiles,
        "canonical": canonical,
        "MW": round(Descriptors.MolWt(molecule), 2),
        "logP": round(Descriptors.MolLogP(molecule), 2),
        "HBD": rdMolDescriptors.CalcNumHBD(molecule),
        "HBA": rdMolDescriptors.CalcNumHBA(molecule),
        "TPSA": round(rdMolDescriptors.CalcTPSA(molecule), 2),
        "svg_light": molecule_svg(molecule, (1.0, 1.0, 1.0)),
        "svg_dark": molecule_svg(molecule, (9 / 255, 17 / 255, 26 / 255), dark=True),
        "molblock_3d": molblock_3d,
    }


@app.get("/api/molecule-search")
def molecule_search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(results=[])
    if query in search_cache:
        return jsonify(results=search_cache[query])

    known_search_names = {
        "ethanol": "CCO",
        "methane": "C",
        "ammonia": "N",
        "benzene": "c1ccccc1",
        "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
        "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        "glucose": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
        "ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
        "acetaminophen": "CC(=O)Nc1ccc(O)cc1",
        "nicotine": "CN1CCCC1c1cccnc1",
        "pyridine": "c1ccncc1",
        "ethylamine": "CCN",
    }
    lowered = query.lower()
    results = []
    for name, smiles in known_search_names.items():
        if lowered in name.lower() and smiles:
            results.append({"name": name.title(), "smiles": smiles})
        if len(results) >= 6:
            break

    if not results:
        try:
            encoded = urllib.parse.quote(query, safe="")
            direct_url = (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                f"{encoded}/property/IsomericSMILES,SMILES/JSON"
            )
            with urllib.request.urlopen(direct_url, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            properties = data.get("PropertyTable", {}).get("Properties", [])
            if properties:
                smiles = properties[0].get("IsomericSMILES") or properties[0].get("SMILES")
                if smiles:
                    results.append({"name": query.title(), "smiles": smiles})
        except Exception:
            pass

    search_cache[query] = results
    return jsonify(results=results)


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("smiles"), list):
        return jsonify(error="Expected a JSON object with a list of SMILES strings."), 400
    if any(not isinstance(smiles, str) for smiles in data["smiles"]):
        return jsonify(error="Every SMILES entry must be a string."), 400

    supplied_names = data.get("names", [])
    if not isinstance(supplied_names, list):
        supplied_names = []

    results = []
    errors = []
    for index, smiles in enumerate(data["smiles"]):
        supplied_name = supplied_names[index] if index < len(supplied_names) else None
        if not isinstance(supplied_name, str):
            supplied_name = None
        try:
            results.append(analyze_smiles(smiles, supplied_name))
        except (ValueError, RuntimeError) as error:
            errors.append({"smiles": smiles, "message": str(error)})

    return jsonify(results=results, errors=errors)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
