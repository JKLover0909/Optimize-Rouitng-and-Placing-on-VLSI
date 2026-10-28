# CLAUDE.md

## Overview
Thesis project on VLSI placement and routing optimization: runs DREAMPlace / MaskPlace (RL macro placement) on ISPD2005 `adaptec*` benchmarks, converts placement to routing input, routes with NTHU-Route, and visualizes congestion.

## Layout
- `Thesis/src/` — pipeline scripts: `makePL*.py` (combine macro / std-cell / fixed / movable placements), `makegraph*.py`, `compute_centrality.py`, `Placement_to_routing_converter.py`, `visualize_routing.py`, `rankplace_merger.py`, `dreamplace_gui.py` (Streamlit).
- `Thesis/CodeCrossServer/` — MaskPlace-style RL code (`PPO2.py`, `place_env/`, `place_db*.py`, `ariane/` protobuf netlist).
- `Thesis/routing_results/<bench>_<mode>_<timestamp>/` — routing outputs (`.gr`, `output`, `routing_visualize/*.png`); thesis results, do not delete or rewrite.
- `Thesis/DREAMPlace`, `Thesis/MaskPlace`, `Thesis/nthu-route` — gitlinks to upstream tools, no `.gitmodules`, so empty after a plain clone.
- `Thesis/*.md`, `Thesis/MASKPLACE_SETUP.txt` — setup / usage notes (MaskPlace centrality, model management); `Thesis/README.md` — command cheat sheet.
- `VLSI.pdf`, `REVISION RESPONSE.pdf`, `adaptec1.gp.pl`, comparison PNGs.

## Commands (from Thesis/README.md)
- DREAMPlace in Docker: `docker run --gpus all -it -v "$(pwd)":/DREAMPlace limbo018/dreamplace:cuda bash`, then `python dreamplace/Placer.py test/ispd2005/adaptec1.json`.
- Placement variants: `python makePL_macro.py adaptec1 1000`, `makePL_stdcell.py`, `makePL_fixed.py`, `makePL_movable.py`.
- Full run: `./run_dreamplace.sh adaptec1`; GUI: `streamlit run dreamplace_gui.py`.

## Rules
- Never commit logs (`nohup.out`, `ngrok.log` — they leaked a server IP and are gitignored now), checkpoints or `__pycache__`.
- Do not modify files under `Thesis/routing_results/`; add new runs as new timestamped folders.
- Do not "fix" the three gitlinks without being asked.
- Keep tokens/IPs out of the repo; use env vars.
