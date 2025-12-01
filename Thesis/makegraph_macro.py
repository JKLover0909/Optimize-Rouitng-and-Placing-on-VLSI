#!/usr/bin/env python3
"""
PageRank Calculator for ISPD Benchmark Netlists - MACRO ONLY VERSION
Parses Bookshelf format and computes PageRank for macro blocks only
"""

import os
import sys
import argparse
from pathlib import Path
import networkx as nx


def parse_nodes_file(nodes_path):
    """
    Parse .nodes file to extract cell/macro names
    Returns: dict {cell_name: {'width': w, 'height': h, 'is_terminal': bool}}
    """
    nodes = {}
    with open(nodes_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            if line.startswith('NumNodes') or line.startswith('NumTerminals'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                width = float(parts[1])
                height = float(parts[2])
                is_terminal = 'terminal' in line.lower()
                nodes[node_name] = {
                    'width': width,
                    'height': height,
                    'is_terminal': is_terminal
                }
    
    return nodes


def identify_macros(nodes, area_threshold=1000):
    """
    Identify macro blocks based on area threshold
    Returns: set of macro names
    """
    macros = set()
    for node_name, info in nodes.items():
        area = info['width'] * info['height']
        if area >= area_threshold:
            macros.add(node_name)
    
    return macros


def parse_nets_file(nets_path):
    """
    Parse .nets file to extract net connectivity
    Returns: list of nets, each net = [driver, sink1, sink2, ...]
    """
    nets = []
    current_net = []
    current_net_name = None
    
    with open(nets_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith('UCLA'):
                continue
            if line.startswith('NumNets') or line.startswith('NumPins'):
                continue
            
            # Start of new net
            if line.startswith('NetDegree'):
                # Save previous net if exists
                if current_net:
                    nets.append({
                        'name': current_net_name,
                        'pins': current_net
                    })
                
                # Parse net name
                parts = line.split()
                if len(parts) >= 3:
                    current_net_name = parts[2]  # "NetDegree : 4   n0" -> n0
                else:
                    current_net_name = f"net_{len(nets)}"
                current_net = []
            else:
                # Pin line: "o197239	I : -0.500000	-6.000000"
                parts = line.split()
                if len(parts) >= 2:
                    pin_name = parts[0]
                    direction = parts[1]  # I (input) or O (output)
                    current_net.append({
                        'node': pin_name,
                        'dir': direction
                    })
        
        # Save last net
        if current_net:
            nets.append({
                'name': current_net_name,
                'pins': current_net
            })
    
    return nets


def build_macro_graph(nets, macros):
    """
    Build directed graph containing only macro-to-macro connections
    For each net: if it connects macros, create edges between them
    """
    G = nx.DiGraph()
    
    # Add all macros as nodes (even isolated ones)
    for macro in macros:
        G.add_node(macro)
    
    macro_connections = 0
    
    for net in nets:
        pins = net['pins']
        
        # Filter only macro pins
        macro_pins = [p for p in pins if p['node'] in macros]
        
        # Skip nets that don't connect macros
        if len(macro_pins) < 2:
            continue
        
        # Find driver macro
        drivers = [p['node'] for p in macro_pins if p['dir'] == 'O']
        sinks = [p['node'] for p in macro_pins if p['dir'] == 'I']
        
        # If no explicit driver, assume first macro is driver
        if not drivers and sinks:
            drivers = [macro_pins[0]['node']]
            sinks = [p['node'] for p in macro_pins[1:]]
        
        # Create edges between macros
        for driver in drivers:
            for sink in sinks:
                if driver != sink:  # Avoid self-loops
                    macro_connections += 1
                    if G.has_edge(driver, sink):
                        # Multiple nets between same macros - increase weight
                        G[driver][sink]['weight'] += 1
                        G[driver][sink]['nets'].append(net['name'])
                    else:
                        G.add_edge(driver, sink, weight=1, nets=[net['name']])
    
    print(f"  Macro-to-macro connections: {macro_connections}")
    
    return G


def calculate_pagerank(G, damping=0.85, max_iter=100):
    """
    Calculate PageRank for all nodes in graph
    """
    if G.number_of_nodes() == 0:
        return {}
    
    try:
        pr = nx.pagerank(G, alpha=damping, max_iter=max_iter, tol=1e-6)
    except:
        # If convergence fails, try with more iterations
        print("Warning: PageRank didn't converge, trying with more iterations...")
        try:
            pr = nx.pagerank(G, alpha=damping, max_iter=500, tol=1e-4)
        except:
            # If still fails, use uniform distribution
            print("Warning: Using uniform distribution for isolated graph")
            pr = {node: 1.0/G.number_of_nodes() for node in G.nodes()}
    
    return pr


def main():
    parser = argparse.ArgumentParser(
        description='Calculate PageRank for MACRO blocks only in ISPD benchmark'
    )
    parser.add_argument(
        'benchmark_path',
        type=str,
        help='Path to benchmark directory (e.g., .../ispd2005/adaptec1)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=1000,
        help='Area threshold for identifying macros (default: 1000)'
    )
    parser.add_argument(
        '--damping',
        type=float,
        default=0.85,
        help='PageRank damping factor (default: 0.85)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (default: <benchmark_name>_macro_result.txt)'
    )
    
    args = parser.parse_args()
    
    # Parse benchmark path
    benchmark_path = Path(args.benchmark_path)
    if not benchmark_path.exists():
        print(f"Error: Benchmark path does not exist: {benchmark_path}")
        sys.exit(1)
    
    benchmark_name = benchmark_path.name
    
    # Find .nodes and .nets files
    nodes_file = benchmark_path / f"{benchmark_name}.nodes"
    nets_file = benchmark_path / f"{benchmark_name}.nets"
    
    if not nodes_file.exists():
        print(f"Error: .nodes file not found: {nodes_file}")
        sys.exit(1)
    
    if not nets_file.exists():
        print(f"Error: .nets file not found: {nets_file}")
        sys.exit(1)
    
    print(f"Processing benchmark: {benchmark_name}")
    print(f"Reading nodes from: {nodes_file}")
    print(f"Reading nets from: {nets_file}")
    print(f"Macro area threshold: {args.threshold}")
    
    # Parse files
    print("\n[1/5] Parsing nodes file...")
    nodes = parse_nodes_file(nodes_file)
    print(f"  Found {len(nodes)} total nodes")
    
    print("\n[2/5] Identifying macro blocks...")
    macros = identify_macros(nodes, area_threshold=args.threshold)
    print(f"  Found {len(macros)} macros (area >= {args.threshold})")
    
    if len(macros) == 0:
        print("Error: No macros found! Try lowering --threshold")
        sys.exit(1)
    
    print("\n[3/5] Parsing nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Found {len(nets)} nets")
    
    # Build macro-only graph
    print("\n[4/5] Building macro-only directed graph...")
    G = build_macro_graph(nets, macros)
    print(f"  Macro graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # Calculate PageRank
    print(f"\n[5/5] Calculating PageRank for macros (damping={args.damping})...")
    pagerank_scores = calculate_pagerank(G, damping=args.damping)
    
    # Sort by PageRank score (descending)
    sorted_macros = sorted(
        pagerank_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Determine output file
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path(f"{benchmark_name}_macro_result.txt")
    
    # Write results
    print(f"\nWriting results to: {output_file}")
    with open(output_file, 'w') as f:
        f.write(f"PageRank Results for MACROS in {benchmark_name}\n")
        f.write(f"{'='*70}\n")
        f.write(f"Total macros: {len(sorted_macros)}\n")
        f.write(f"Area threshold: {args.threshold}\n")
        f.write(f"Damping factor: {args.damping}\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"{'Rank':<8} {'Macro':<30} {'PageRank':<15} {'Width':<10} {'Height':<10} {'Area':<12}\n")
        f.write(f"{'-'*95}\n")
        
        for rank, (macro, score) in enumerate(sorted_macros, 1):
            info = nodes[macro]
            width = info['width']
            height = info['height']
            area = width * height
            f.write(f"{rank:<8} {macro:<30} {score:<15.8f} {width:<10.1f} {height:<10.1f} {area:<12.1f}\n")
    
    # Print statistics
    print("\n" + "="*70)
    print("MACRO RANKING SUMMARY")
    print("="*70)
    
    # Top 10
    print(f"\n{'Rank':<8} {'Macro':<30} {'PageRank':<15} {'Area':<12}")
    print("-" * 70)
    for rank, (macro, score) in enumerate(sorted_macros[:min(10, len(sorted_macros))], 1):
        info = nodes[macro]
        area = info['width'] * info['height']
        print(f"{rank:<8} {macro:<30} {score:<15.8f} {area:<12.1f}")
    
    if len(sorted_macros) > 10:
        print(f"\n... (showing top 10 of {len(sorted_macros)} macros)")
    
    # Placement suggestions
    print("\n" + "="*70)
    print("PLACEMENT SUGGESTIONS")
    print("="*70)
    
    high_rank_macros = sorted_macros[:max(1, len(sorted_macros)//3)]
    mid_rank_macros = sorted_macros[len(sorted_macros)//3:2*len(sorted_macros)//3]
    low_rank_macros = sorted_macros[2*len(sorted_macros)//3:]
    
    print(f"\n🔴 HIGH PRIORITY ({len(high_rank_macros)} macros): Place near DIE CENTER")
    print(f"   PageRank range: {high_rank_macros[-1][1]:.6f} - {high_rank_macros[0][1]:.6f}")
    for rank, (macro, score) in enumerate(high_rank_macros[:5], 1):
        print(f"   {rank}. {macro} (score: {score:.6f})")
    
    print(f"\n🟡 MEDIUM PRIORITY ({len(mid_rank_macros)} macros): Place in MIDDLE ZONE")
    if mid_rank_macros:
        print(f"   PageRank range: {mid_rank_macros[-1][1]:.6f} - {mid_rank_macros[0][1]:.6f}")
    
    print(f"\n🟢 LOW PRIORITY ({len(low_rank_macros)} macros): Place near DIE EDGES")
    if low_rank_macros:
        print(f"   PageRank range: {low_rank_macros[-1][1]:.6f} - {low_rank_macros[0][1]:.6f}")
    
    print(f"\n✓ Done! Full results saved to: {output_file.absolute()}")


if __name__ == "__main__":
    main()
