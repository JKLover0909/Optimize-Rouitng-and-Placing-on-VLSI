#!/usr/bin/env python3
"""
makePL_fixed.py - Reorder .pl file with FIXED components sorted by PageRank first
Only FIXED/terminal components are ranked and placed at the top.
Movable components remain at the bottom in original order.
"""

import sys
import os
import networkx as nx
from collections import defaultdict

def parse_nodes_file(nodes_file):
    """Parse .nodes file to extract terminal/fixed status."""
    terminals = set()
    
    with open(nodes_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                if 'terminal' in line.lower():
                    terminals.add(node_name)
    
    return terminals

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

def build_fixed_graph(nets, fixed_components, terminals):
    """Build directed graph considering only fixed-to-fixed connections."""
    # Combine FIXED from .pl and terminals from .nodes
    all_fixed = fixed_components | terminals
    
    G = nx.DiGraph()
    
    # Add all fixed components as nodes
    for fixed_comp in all_fixed:
        G.add_node(fixed_comp)
    
    # Process each net
    for net in nets:
        # Filter pins to only include fixed components
        fixed_pins = [(node, direction) for node, direction in net if node in all_fixed]
        
        if len(fixed_pins) < 2:
            continue
        
        # Find drivers (O) and sinks (I or B)
        drivers = [node for node, direction in fixed_pins if direction == 'O']
        sinks = [node for node, direction in fixed_pins if direction in ['I', 'B']]
        
        # If no explicit driver, treat first pin as driver
        if not drivers and fixed_pins:
            drivers = [fixed_pins[0][0]]
            sinks = [node for node, _ in fixed_pins[1:]]
        
        # Add edges: driver -> sinks
        for driver in drivers:
            for sink in sinks:
                if driver != sink:
                    if G.has_edge(driver, sink):
                        G[driver][sink]['weight'] += 1
                    else:
                        G.add_edge(driver, sink, weight=1)
    
    return G, all_fixed

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
        
        for placement in placements:
            fixed_str = " /FIXED" if placement['fixed'] else ""
            f.write(f"{placement['node']}\t{placement['x']:.6f}\t{placement['y']:.6f}\t: {placement['orientation']}{fixed_str}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python makePL_fixed.py <benchmark_name>")
        print("Example: python makePL_fixed.py adaptec1")
        sys.exit(1)
    
    benchmark = sys.argv[1]
    
    # File paths
    base_dir = "DREAMPlace/install/benchmarks/ispd2005"
    benchmark_dir = f"{base_dir}/{benchmark}"
    nodes_file = f"{benchmark_dir}/{benchmark}.nodes"
    nets_file = f"{benchmark_dir}/{benchmark}.nets"
    pl_file = f"{benchmark_dir}/{benchmark}.pl"
    
    print(f"=== FIXED-ONLY PageRank PL Reordering ===")
    print(f"Benchmark: {benchmark}")
    print()
    
    # Step 1: Parse nodes to identify terminals
    print("Step 1: Parsing .nodes file...")
    terminals = parse_nodes_file(nodes_file)
    print(f"  Terminals from .nodes: {len(terminals)}")
    print()
    
    # Step 2: Parse .pl file to get FIXED components
    print("Step 2: Parsing .pl file...")
    placements, fixed_from_pl = parse_pl_file(pl_file)
    print(f"  Total placements: {len(placements)}")
    print(f"  FIXED from .pl: {len(fixed_from_pl)}")
    print()
    
    # Step 3: Parse nets
    print("Step 3: Parsing .nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Total nets: {len(nets)}")
    print()
    
    # Step 4: Build fixed-only graph
    print("Step 4: Building fixed-component-only graph...")
    G, all_fixed = build_fixed_graph(nets, fixed_from_pl, terminals)
    print(f"  Total FIXED components: {len(all_fixed)}")
    print(f"  Graph nodes: {G.number_of_nodes()}")
    print(f"  Graph edges: {G.number_of_edges()}")
    print()
    
    # Step 5: Calculate PageRank
    print("Step 5: Calculating PageRank...")
    pagerank_scores = calculate_pagerank(G)
    
    if pagerank_scores:
        sorted_fixed = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        print(f"  Top 5 FIXED components by PageRank:")
        for i, (node, score) in enumerate(sorted_fixed[:5], 1):
            print(f"    {i}. {node}: {score:.8f}")
    print()
    
    # Step 6: Separate and sort placements
    print("Step 6: Reordering placements...")
    fixed_placements = []
    movable_placements = []
    
    for placement in placements:
        if placement['node'] in all_fixed:
            fixed_placements.append(placement)
        else:
            movable_placements.append(placement)
    
    # Sort fixed components by PageRank (descending)
    fixed_placements.sort(
        key=lambda p: pagerank_scores.get(p['node'], 0),
        reverse=True
    )
    
    # Combine: fixed first (sorted by PageRank), then movable (original order)
    reordered_placements = fixed_placements + movable_placements
    
    print(f"  FIXED components (sorted by PageRank): {len(fixed_placements)}")
    print(f"  Movable components (original order): {len(movable_placements)}")
    print()
    
    # Step 7: Write reordered .pl file
    print("Step 7: Writing reordered .pl file...")
    write_pl_file(pl_file, reordered_placements)
    print(f"  ✓ File updated: {pl_file}")
    print()
    
    print("=== Reordering Complete ===")

if __name__ == "__main__":
    main()
