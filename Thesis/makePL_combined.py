#!/usr/bin/env python3
"""
makePL_combined.py - Reorder .pl file based on PageRank with combined filtering
Supports filtering by:
  - Component type: macro (height > row_height) or stdcell (height <= row_height)
  - Placement status: movable or fixed

Usage:
    python makePL_combined.py <benchmark> <component_type> <placement_status>
    
    component_type: "global", "macro", or "stdcell"
    placement_status: "all", "movable", or "fixed" (ignored if component_type is "global")

Example:
    python makePL_combined.py adaptec1 macro movable
    python makePL_combined.py adaptec1 stdcell fixed
    python makePL_combined.py adaptec1 global all
"""

import sys
import os
import networkx as nx
from collections import defaultdict

# Base directory for benchmarks
BASE_DIR = "DREAMPlace/install/benchmarks/ispd2005"


def parse_scl_file(scl_file):
    """Parse .scl file to extract row height."""
    row_height = None
    
    with open(scl_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('Height'):
                parts = line.split(':')
                if len(parts) >= 2:
                    try:
                        row_height = float(parts[1].strip())
                        break
                    except ValueError:
                        continue
    
    if row_height is None:
        print("Warning: Could not find row height in .scl file, using default 12")
        row_height = 12
    
    return row_height


def parse_nodes_file(nodes_file):
    """Parse .nodes file to extract all components with their dimensions."""
    components = {}
    
    with open(nodes_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            if line.startswith('NumNodes') or line.startswith('NumTerminals'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                try:
                    width = float(parts[1])
                    height = float(parts[2])
                    is_terminal = 'terminal' in line.lower()
                    components[node_name] = {
                        'width': width,
                        'height': height,
                        'area': width * height,
                        'terminal': is_terminal
                    }
                except ValueError:
                    continue
    
    return components


def parse_nets_file(nets_file):
    """Parse .nets file to extract hypergraph connectivity."""
    nets = []
    current_pins = []
    
    with open(nets_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            if line.startswith('NumNets') or line.startswith('NumPins'):
                continue
            
            if line.startswith('NetDegree'):
                if current_pins:
                    nets.append(current_pins)
                current_pins = []
            else:
                parts = line.split()
                if parts:
                    node_name = parts[0]
                    direction = parts[1] if len(parts) > 1 else 'B'
                    current_pins.append((node_name, direction))
        
        if current_pins:
            nets.append(current_pins)
    
    return nets


def parse_pl_file(pl_file):
    """Parse .pl file and extract placement information including FIXED status."""
    placements = []
    fixed_components = set()
    
    with open(pl_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                node_name = parts[0]
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    orientation = parts[4] if len(parts) > 4 else 'N'
                    is_fixed = '/FIXED' in line
                    
                    placements.append({
                        'node': node_name,
                        'x': x,
                        'y': y,
                        'orientation': orientation,
                        'fixed': is_fixed
                    })
                    
                    if is_fixed:
                        fixed_components.add(node_name)
                        
                except ValueError:
                    continue
    
    return placements, fixed_components


def classify_components(components, row_height):
    """Classify components into macros and standard cells based on row height."""
    macros = set()
    stdcells = set()
    
    for name, info in components.items():
        if info['height'] > row_height:
            macros.add(name)
        else:
            stdcells.add(name)
    
    return macros, stdcells


def filter_components(components, macros, stdcells, fixed_components, terminals,
                      component_type, placement_status):
    """
    Filter components based on type and placement status.
    
    component_type: "global", "macro", or "stdcell"
    placement_status: "all", "movable", or "fixed"
    """
    # Start with all components
    if component_type == "global":
        filtered = set(components.keys())
    elif component_type == "macro":
        filtered = macros.copy()
    elif component_type == "stdcell":
        filtered = stdcells.copy()
    else:
        raise ValueError(f"Unknown component_type: {component_type}")
    
    # Apply placement status filter (only if not global)
    if component_type != "global" and placement_status != "all":
        all_fixed = fixed_components | terminals
        
        if placement_status == "movable":
            filtered = {c for c in filtered if c not in all_fixed}
        elif placement_status == "fixed":
            filtered = {c for c in filtered if c in all_fixed}
        else:
            raise ValueError(f"Unknown placement_status: {placement_status}")
    
    return filtered


def build_graph(nets, target_components):
    """Build directed graph considering only connections between target components."""
    G = nx.DiGraph()
    
    # Add all target components as nodes
    for comp in target_components:
        G.add_node(comp)
    
    # Process each net
    for net in nets:
        # Filter pins to only include target components
        target_pins = [(node, direction) for node, direction in net if node in target_components]
        
        if len(target_pins) < 2:
            continue
        
        # Find drivers (O) and sinks (I or B)
        drivers = [node for node, direction in target_pins if direction == 'O']
        sinks = [node for node, direction in target_pins if direction in ['I', 'B']]
        
        # If no explicit driver, treat first pin as driver
        if not drivers and target_pins:
            drivers = [target_pins[0][0]]
            sinks = [node for node, _ in target_pins[1:]]
        
        # Add edges: driver -> sinks
        for driver in drivers:
            for sink in sinks:
                if driver != sink:
                    if G.has_edge(driver, sink):
                        G[driver][sink]['weight'] += 1
                    else:
                        G.add_edge(driver, sink, weight=1)
    
    return G


def calculate_pagerank(G, alpha=0.85, max_iter=100):
    """Calculate PageRank scores for the graph."""
    if len(G.nodes()) == 0:
        return {}
    
    try:
        pagerank_scores = nx.pagerank(G, alpha=alpha, max_iter=max_iter, weight='weight')
        return pagerank_scores
    except:
        # If PageRank fails, return uniform scores
        uniform_score = 1.0 / len(G.nodes())
        return {node: uniform_score for node in G.nodes()}


def write_pl_file(pl_file, placements):
    """Write placements to .pl file."""
    with open(pl_file, 'w') as f:
        f.write("UCLA pl 1.0\n\n")
        
        for p in placements:
            line = f"{p['node']}\t{p['x']:.6f}\t{p['y']:.6f}\t:\t{p['orientation']}"
            if p['fixed']:
                line += "\t/FIXED"
            f.write(line + "\n")


def reorder_placements(placements, target_components, pagerank_scores):
    """
    Reorder placements: target components sorted by PageRank first,
    then remaining components in original order.
    """
    # Separate placements
    target_placements = []
    other_placements = []
    
    for p in placements:
        if p['node'] in target_components:
            target_placements.append(p)
        else:
            other_placements.append(p)
    
    # Sort target placements by PageRank score (descending)
    target_placements.sort(key=lambda p: pagerank_scores.get(p['node'], 0), reverse=True)
    
    # Combine: target first, then others
    return target_placements + other_placements


def main():
    if len(sys.argv) < 4:
        print("Usage: python makePL_combined.py <benchmark> <component_type> <placement_status>")
        print("  component_type: global, macro, stdcell")
        print("  placement_status: all, movable, fixed")
        print("\nExamples:")
        print("  python makePL_combined.py adaptec1 global all")
        print("  python makePL_combined.py adaptec1 macro movable")
        print("  python makePL_combined.py adaptec1 stdcell fixed")
        sys.exit(1)
    
    benchmark = sys.argv[1]
    component_type = sys.argv[2].lower()
    placement_status = sys.argv[3].lower()
    
    # Validate arguments
    if component_type not in ["global", "macro", "stdcell"]:
        print(f"Error: Invalid component_type '{component_type}'")
        print("Valid options: global, macro, stdcell")
        sys.exit(1)
    
    if placement_status not in ["all", "movable", "fixed"]:
        print(f"Error: Invalid placement_status '{placement_status}'")
        print("Valid options: all, movable, fixed")
        sys.exit(1)
    
    # Build file paths
    benchmark_dir = f"{BASE_DIR}/{benchmark}"
    nodes_file = f"{benchmark_dir}/{benchmark}.nodes"
    nets_file = f"{benchmark_dir}/{benchmark}.nets"
    pl_file = f"{benchmark_dir}/{benchmark}.pl"
    scl_file = f"{benchmark_dir}/{benchmark}.scl"
    
    # Check files exist
    for filepath in [nodes_file, nets_file, pl_file, scl_file]:
        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}")
            sys.exit(1)
    
    print(f"=" * 60)
    print(f"makePL_combined.py - PageRank-based Placement Reordering")
    print(f"=" * 60)
    print(f"Benchmark: {benchmark}")
    print(f"Component type: {component_type}")
    print(f"Placement status: {placement_status}")
    print(f"-" * 60)
    
    # Parse files
    print("Parsing .scl file...")
    row_height = parse_scl_file(scl_file)
    print(f"  Row height: {row_height}")
    
    print("Parsing .nodes file...")
    components = parse_nodes_file(nodes_file)
    print(f"  Total components: {len(components)}")
    
    print("Parsing .nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Total nets: {len(nets)}")
    
    print("Parsing .pl file...")
    placements, fixed_components = parse_pl_file(pl_file)
    print(f"  Total placements: {len(placements)}")
    print(f"  Fixed components: {len(fixed_components)}")
    
    # Find terminals from .nodes
    terminals = {name for name, info in components.items() if info['terminal']}
    print(f"  Terminal components: {len(terminals)}")
    
    # Classify components
    print("\nClassifying components by row height...")
    macros, stdcells = classify_components(components, row_height)
    print(f"  Macros (height > {row_height}): {len(macros)}")
    print(f"  Standard cells (height <= {row_height}): {len(stdcells)}")
    
    # Filter target components
    print(f"\nFiltering target components...")
    target_components = filter_components(
        components, macros, stdcells, fixed_components, terminals,
        component_type, placement_status
    )
    print(f"  Target components: {len(target_components)}")
    
    if len(target_components) == 0:
        print("\nWarning: No components match the filter criteria!")
        print("The .pl file will remain unchanged.")
        sys.exit(0)
    
    # Build graph and calculate PageRank
    print("\nBuilding connectivity graph...")
    G = build_graph(nets, target_components)
    print(f"  Nodes: {len(G.nodes())}")
    print(f"  Edges: {len(G.edges())}")
    
    print("\nCalculating PageRank scores...")
    pagerank_scores = calculate_pagerank(G)
    
    if pagerank_scores:
        # Show top 10 components
        sorted_scores = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        print("\nTop 10 components by PageRank:")
        for i, (node, score) in enumerate(sorted_scores[:10], 1):
            print(f"  {i}. {node}: {score:.6f}")
    
    # Reorder placements
    print("\nReordering placements...")
    new_placements = reorder_placements(placements, target_components, pagerank_scores)
    
    # Write new .pl file
    print(f"\nWriting new .pl file...")
    write_pl_file(pl_file, new_placements)
    print(f"  Output: {pl_file}")
    
    print(f"\n{'=' * 60}")
    print("Done!")
    print(f"{'=' * 60}")
    
    # Summary
    mode_desc = component_type
    if component_type != "global":
        mode_desc += f" + {placement_status}"
    print(f"\nSummary:")
    print(f"  Mode: {mode_desc}")
    print(f"  Components reordered: {len(target_components)}")
    print(f"  Components unchanged: {len(placements) - len(target_components)}")


if __name__ == "__main__":
    main()
