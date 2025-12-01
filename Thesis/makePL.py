#!/usr/bin/env python3
"""
PageRank-based PL File Reordering
Reorder nodes in .pl file based on PageRank scores (high to low)
Keeps coordinates unchanged, only changes line order
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
import networkx as nx


def parse_nodes_file(nodes_path):
    """
    Parse .nodes file to extract cell/macro names and identify terminals
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
                    current_net_name = parts[2]
                else:
                    current_net_name = f"net_{len(nets)}"
                current_net = []
            else:
                # Pin line
                parts = line.split()
                if len(parts) >= 2:
                    pin_name = parts[0]
                    direction = parts[1]
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
                if driver != sink:
                    if G.has_edge(driver, sink):
                        G[driver][sink]['weight'] += 1
                    else:
                        G.add_edge(driver, sink, weight=1)
    
    return G


def calculate_pagerank(G, damping=0.85):
    """
    Calculate PageRank for all nodes in graph
    """
    try:
        pr = nx.pagerank(G, alpha=damping, max_iter=100, tol=1e-6)
    except:
        print("Warning: PageRank didn't converge, trying with more iterations...")
        try:
            pr = nx.pagerank(G, alpha=damping, max_iter=500, tol=1e-4)
        except:
            print("Warning: Using uniform distribution")
            pr = {node: 1.0/G.number_of_nodes() for node in G.nodes()}
    
    return pr


def parse_pl_file(pl_path):
    """
    Parse .pl file to extract node coordinates
    Returns: (header_lines, node_dict)
        header_lines: list of comment/header lines
        node_dict: {node_name: {'x': x, 'y': y, 'orient': o, 'fixed': bool, 'line': original_line}}
    """
    header_lines = []
    nodes = {}
    
    with open(pl_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            
            # Header or comment lines
            if not stripped or stripped.startswith('#') or stripped.startswith('UCLA'):
                header_lines.append(line.rstrip('\n'))
                continue
            
            # Node placement line: "o0	0	0	: N"
            parts = stripped.split()
            if len(parts) >= 4:
                node_name = parts[0]
                x = parts[1]
                y = parts[2]
                # Skip colon
                orient = parts[4] if len(parts) > 4 else 'N'
                fixed = '/FIXED' in stripped or 'FIXED' in stripped.upper()
                
                nodes[node_name] = {
                    'x': x,
                    'y': y,
                    'orient': orient,
                    'fixed': fixed,
                    'line': line.rstrip('\n')
                }
    
    return header_lines, nodes


def write_pl_file(output_path, header_lines, sorted_nodes, pl_nodes):
    """
    Write new .pl file with nodes sorted by PageRank
    """
    with open(output_path, 'w') as f:
        # Write header
        for line in header_lines:
            f.write(line + '\n')
        
        # Write nodes in PageRank order
        for node_name in sorted_nodes:
            if node_name in pl_nodes:
                node_info = pl_nodes[node_name]
                x = node_info['x']
                y = node_info['y']
                orient = node_info['orient']
                fixed = node_info['fixed']
                
                # Reconstruct line
                line = f"{node_name}\t{x}\t{y}\t: {orient}"
                if fixed:
                    line += " /FIXED"
                
                f.write(line + '\n')


def main():
    parser = argparse.ArgumentParser(
        description='Reorder .pl file based on PageRank scores'
    )
    parser.add_argument(
        'benchmark_name',
        type=str,
        help='Benchmark name (e.g., adaptec1, bigblue1)'
    )
    parser.add_argument(
        '--damping',
        type=float,
        default=0.85,
        help='PageRank damping factor (default: 0.85)'
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        default=True,
        help='Backup original .pl file to .pl.old (default: True)'
    )
    
    args = parser.parse_args()
    
    # Build benchmark path
    base_dir = "/home/ubuntu/vnet/Thesis/DREAMPlace/install/benchmarks/ispd2005"
    benchmark_path = Path(base_dir) / args.benchmark_name
    if not benchmark_path.exists():
        print(f"Error: Benchmark path does not exist: {benchmark_path}")
        sys.exit(1)
    
    benchmark_name = benchmark_path.name
    
    # Find required files
    nodes_file = benchmark_path / f"{benchmark_name}.nodes"
    nets_file = benchmark_path / f"{benchmark_name}.nets"
    pl_file = benchmark_path / f"{benchmark_name}.pl"
    
    if not nodes_file.exists():
        print(f"Error: .nodes file not found: {nodes_file}")
        sys.exit(1)
    
    if not nets_file.exists():
        print(f"Error: .nets file not found: {nets_file}")
        sys.exit(1)
    
    if not pl_file.exists():
        print(f"Error: .pl file not found: {pl_file}")
        sys.exit(1)
    
    print(f"Processing benchmark: {benchmark_name}")
    print(f"Reading nodes from: {nodes_file}")
    print(f"Reading nets from: {nets_file}")
    print(f"Reading placements from: {pl_file}")
    
    # Parse files
    print("\n[1/6] Parsing nodes file...")
    nodes = parse_nodes_file(nodes_file)
    print(f"  Found {len(nodes)} nodes")
    terminal_count = sum(1 for n in nodes.values() if n['is_terminal'])
    print(f"  Terminal nodes: {terminal_count}")
    
    print("\n[2/6] Parsing nets file...")
    nets = parse_nets_file(nets_file)
    print(f"  Found {len(nets)} nets")
    
    print("\n[3/6] Building directed graph...")
    G = build_graph_from_nets(nets)
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    print(f"\n[4/6] Calculating PageRank (damping={args.damping})...")
    pagerank_scores = calculate_pagerank(G, damping=args.damping)
    print(f"  Computed PageRank for {len(pagerank_scores)} nodes")
    
    # Sort by PageRank (descending)
    sorted_by_pagerank = sorted(
        pagerank_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Extract node names in sorted order
    sorted_node_names = [node for node, score in sorted_by_pagerank]
    
    print("\n[5/6] Parsing placement file...")
    header_lines, pl_nodes = parse_pl_file(pl_file)
    print(f"  Found placement info for {len(pl_nodes)} nodes")
    
    # Add nodes from .pl that aren't in PageRank (shouldn't happen, but safety)
    nodes_only_in_pl = set(pl_nodes.keys()) - set(sorted_node_names)
    if nodes_only_in_pl:
        print(f"  Warning: {len(nodes_only_in_pl)} nodes in .pl but not in PageRank")
        sorted_node_names.extend(sorted(nodes_only_in_pl))
    
    # Backup original .pl file
    if args.backup:
        backup_path = pl_file.with_suffix('.pl.old')
        print(f"\n[6/6] Backing up original file to: {backup_path}")
        shutil.copy2(pl_file, backup_path)
    
    # Write new .pl file
    print(f"\nWriting reordered .pl file to: {pl_file}")
    write_pl_file(pl_file, header_lines, sorted_node_names, pl_nodes)
    
    # Print top 20 for verification
    print("\n" + "="*70)
    print("TOP 20 NODES BY PAGERANK (now at top of .pl file)")
    print("="*70)
    print(f"{'Rank':<8} {'Node':<30} {'PageRank':<15} {'X':<10} {'Y':<10} {'Fixed':<8}")
    print("-" * 95)
    
    for rank, node_name in enumerate(sorted_node_names[:20], 1):
        score = pagerank_scores.get(node_name, 0.0)
        pl_info = pl_nodes.get(node_name, {})
        x = pl_info.get('x', 'N/A')
        y = pl_info.get('y', 'N/A')
        fixed = 'Yes' if pl_info.get('fixed', False) else 'No'
        
        # Check if macro
        node_info = nodes.get(node_name, {})
        width = node_info.get('width', 0)
        height = node_info.get('height', 0)
        area = width * height
        marker = " [MACRO]" if area > 1000 else ""
        
        print(f"{rank:<8} {node_name:<30} {score:<15.8f} {x:<10} {y:<10} {fixed:<8}{marker}")
    
    print(f"\n✓ Done! .pl file has been reordered by PageRank")
    print(f"  Original backup: {backup_path if args.backup else 'N/A'}")
    print(f"  New sorted file: {pl_file}")
    print(f"\nNote: Coordinates unchanged, only line order sorted by PageRank (high → low)")


if __name__ == "__main__":
    main()
