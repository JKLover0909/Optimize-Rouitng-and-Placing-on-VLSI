#!/usr/bin/env python3
"""
PageRank Calculator for ISPD Benchmark Netlists
Parses Bookshelf format and computes PageRank for all components
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


def build_graph_from_nets(nets):
    """
    Build directed graph from nets using driver-driven model
    For each net: driver (O pin) -> sinks (I pins)
    """
    G = nx.DiGraph()
    
    for net in nets:
        pins = net['pins']
        
        # Find driver (output pin)
        drivers = [p['node'] for p in pins if p['dir'] == 'O']
        sinks = [p['node'] for p in pins if p['dir'] == 'I']
        
        # If no explicit driver, assume first pin is driver
        if not drivers and sinks:
            drivers = [pins[0]['node']]
            sinks = [p['node'] for p in pins[1:]]
        
        # Create edges from each driver to each sink
        for driver in drivers:
            for sink in sinks:
                if driver != sink:  # Avoid self-loops
                    # Add edge with net name as attribute
                    if G.has_edge(driver, sink):
                        # Multiple nets between same nodes - increase weight
                        G[driver][sink]['weight'] += 1
                        G[driver][sink]['nets'].append(net['name'])
                    else:
                        G.add_edge(driver, sink, weight=1, nets=[net['name']])
    
    return G


def calculate_pagerank(G, damping=0.85, max_iter=100):
    """
    Calculate PageRank for all nodes in graph
    """
    try:
        pr = nx.pagerank(G, alpha=damping, max_iter=max_iter, tol=1e-6)
    except:
        # If convergence fails, try with more iterations
        print("Warning: PageRank didn't converge, trying with more iterations...")
        pr = nx.pagerank(G, alpha=damping, max_iter=500, tol=1e-4)
    
    return pr


def main():
    parser = argparse.ArgumentParser(
        description='Calculate PageRank for ISPD benchmark netlist'
    )
    parser.add_argument(
        'benchmark_path',
        type=str,
        help='Path to benchmark directory (e.g., .../ispd2005/adaptec1)'
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
        help='Output file path (default: <benchmark_name>_result.txt)'
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
    
    # Parse files
    print("\n[1/4] Parsing nodes file...")
    nodes = parse_nodes_file(nodes_file)
    print(f"  Found {len(nodes)} nodes")
    
    print("\n[2/4] Parsing nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Found {len(nets)} nets")
    
    # Build graph
    print("\n[3/4] Building directed graph...")
    G = build_graph_from_nets(nets)
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # Calculate PageRank
    print(f"\n[4/4] Calculating PageRank (damping={args.damping})...")
    pagerank_scores = calculate_pagerank(G, damping=args.damping)
    
    # Sort by PageRank score (descending)
    sorted_nodes = sorted(
        pagerank_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Determine output file
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path(f"{benchmark_name}_result.txt")
    
    # Write results
    print(f"\nWriting results to: {output_file}")
    with open(output_file, 'w') as f:
        f.write(f"PageRank Results for {benchmark_name}\n")
        f.write(f"{'='*60}\n")
        f.write(f"Total components: {len(sorted_nodes)}\n")
        f.write(f"Damping factor: {args.damping}\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"{'Rank':<8} {'Component':<30} {'PageRank Score':<15}\n")
        f.write(f"{'-'*60}\n")
        
        for rank, (node, score) in enumerate(sorted_nodes, 1):
            f.write(f"{rank:<8} {node:<30} {score:<15.8f}\n")
    
    # Print top 20 for verification
    print("\nTop 20 components by PageRank:")
    print(f"{'Rank':<8} {'Component':<30} {'PageRank Score':<15}")
    print("-" * 60)
    for rank, (node, score) in enumerate(sorted_nodes[:20], 1):
        # Check if it's a macro (larger size in nodes dict)
        node_info = nodes.get(node, {})
        width = node_info.get('width', 0)
        height = node_info.get('height', 0)
        area = width * height
        marker = " [MACRO]" if area > 1000 else ""
        print(f"{rank:<8} {node:<30} {score:<15.8f}{marker}")
    
    print(f"\n✓ Done! Results saved to: {output_file.absolute()}")


if __name__ == "__main__":
    main()
