#!/usr/bin/env python3
"""
makePL_stdcell.py - Reorder .pl file with STANDARD CELL components sorted by PageRank first
Only standard cells (small components with area < threshold) are ranked and placed at the top.
Macros remain at the bottom in original order.
"""

import sys
import os
import networkx as nx
from collections import defaultdict

def parse_nodes_file(nodes_file):
    """Parse .nodes file to extract all components with their areas."""
    components = {}
    
    with open(nodes_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                try:
                    width = float(parts[1])
                    height = float(parts[2])
                    area = width * height
                    is_terminal = 'terminal' in line.lower()
                    components[node_name] = {
                        'area': area,
                        'terminal': is_terminal
                    }
                except ValueError:
                    continue
    
    return components

def identify_stdcells(components, area_threshold=1000):
    """Identify standard cell components based on area threshold."""
    stdcells = set()
    for name, info in components.items():
        if info['area'] < area_threshold:
            stdcells.add(name)
    return stdcells

def parse_nets_file(nets_file):
    """Parse .nets file to extract hypergraph connectivity."""
    nets = []
    current_net = None
    current_pins = []
    
    with open(nets_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            
            if line.startswith('NetDegree'):
                if current_net is not None and current_pins:
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

def build_stdcell_graph(nets, stdcells):
    """Build directed graph considering only standard-cell-to-standard-cell connections."""
    G = nx.DiGraph()
    
    # Add all standard cells as nodes
    for stdcell in stdcells:
        G.add_node(stdcell)
    
    # Process each net
    for net in nets:
        # Filter pins to only include standard cells
        stdcell_pins = [(node, direction) for node, direction in net if node in stdcells]
        
        if len(stdcell_pins) < 2:
            continue
        
        # Find drivers (O) and sinks (I or B)
        drivers = [node for node, direction in stdcell_pins if direction == 'O']
        sinks = [node for node, direction in stdcell_pins if direction in ['I', 'B']]
        
        # If no explicit driver, treat first pin as driver
        if not drivers and stdcell_pins:
            drivers = [stdcell_pins[0][0]]
            sinks = [node for node, _ in stdcell_pins[1:]]
        
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

def parse_pl_file(pl_file):
    """Parse .pl file and extract placement information."""
    placements = []
    
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
                except ValueError:
                    continue
    
    return placements

def write_pl_file(pl_file, placements):
    """Write placements to .pl file."""
    with open(pl_file, 'w') as f:
        f.write("UCLA pl 1.0\n\n")
        
        for placement in placements:
            fixed_str = " /FIXED" if placement['fixed'] else ""
            f.write(f"{placement['node']}\t{placement['x']:.6f}\t{placement['y']:.6f}\t: {placement['orientation']}{fixed_str}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python makePL_stdcell.py <benchmark_name> [area_threshold]")
        print("Example: python makePL_stdcell.py adaptec1 1000")
        sys.exit(1)
    
    benchmark = sys.argv[1]
    area_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    # File paths
    base_dir = "DREAMPlace/install/benchmarks/ispd2005"
    benchmark_dir = f"{base_dir}/{benchmark}"
    nodes_file = f"{benchmark_dir}/{benchmark}.nodes"
    nets_file = f"{benchmark_dir}/{benchmark}.nets"
    pl_file = f"{benchmark_dir}/{benchmark}.pl"
    
    print(f"=== STANDARD-CELL-ONLY PageRank PL Reordering ===")
    print(f"Benchmark: {benchmark}")
    print(f"Area threshold: {area_threshold}")
    print()
    
    # Step 1: Parse nodes to identify standard cells
    print("Step 1: Parsing .nodes file...")
    components = parse_nodes_file(nodes_file)
    stdcells = identify_stdcells(components, area_threshold)
    print(f"  Total components: {len(components)}")
    print(f"  Identified standard cells: {len(stdcells)}")
    print()
    
    # Step 2: Parse nets
    print("Step 2: Parsing .nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Total nets: {len(nets)}")
    print()
    
    # Step 3: Build standard-cell-only graph
    print("Step 3: Building standard-cell-only graph...")
    G = build_stdcell_graph(nets, stdcells)
    print(f"  Graph nodes: {G.number_of_nodes()}")
    print(f"  Graph edges: {G.number_of_edges()}")
    print()
    
    # Step 4: Calculate PageRank
    print("Step 4: Calculating PageRank...")
    pagerank_scores = calculate_pagerank(G)
    
    if pagerank_scores:
        sorted_cells = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        print(f"  Top 5 standard cells by PageRank:")
        for i, (node, score) in enumerate(sorted_cells[:5], 1):
            print(f"    {i}. {node}: {score:.8f}")
    print()
    
    # Step 5: Parse current .pl file
    print("Step 5: Parsing .pl file...")
    placements = parse_pl_file(pl_file)
    print(f"  Total placements: {len(placements)}")
    print()
    
    # Step 6: Separate and sort placements
    print("Step 6: Reordering placements...")
    stdcell_placements = []
    other_placements = []
    
    for placement in placements:
        if placement['node'] in stdcells:
            stdcell_placements.append(placement)
        else:
            other_placements.append(placement)
    
    # Sort standard cells by PageRank (descending)
    stdcell_placements.sort(
        key=lambda p: pagerank_scores.get(p['node'], 0),
        reverse=True
    )
    
    # Combine: standard cells first (sorted by PageRank), then others (original order)
    reordered_placements = stdcell_placements + other_placements
    
    print(f"  Standard cells (sorted by PageRank): {len(stdcell_placements)}")
    print(f"  Macros (original order): {len(other_placements)}")
    print()
    
    # Step 7: Write reordered .pl file
    print("Step 7: Writing reordered .pl file...")
    write_pl_file(pl_file, reordered_placements)
    print(f"  ✓ File updated: {pl_file}")
    print()
    
    print("=== Reordering Complete ===")

if __name__ == "__main__":
    main()
