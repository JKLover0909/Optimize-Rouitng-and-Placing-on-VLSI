"""
Compute various centrality metrics for macro nodes in VLSI benchmarks.
Supports: PageRank, Eigenvector Centrality, Betweenness Centrality, etc.
"""

import networkx as nx
import pickle
import argparse
from pathlib import Path
from collections import defaultdict


def parse_nodes_file(nodes_file):
    """Parse .nodes file to get macro information."""
    macros = []
    macro_info = {}
    
    with open(nodes_file, 'r') as f:
        lines = f.readlines()
        
    # Skip header
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('NumNodes'):
            start_idx = i + 1
            break
    
    for line in lines[start_idx:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) < 3:
            continue
            
        node_name = parts[0]
        width = float(parts[1])
        height = float(parts[2])
        
        # Check if this is a terminal (fixed node)
        is_terminal = 'terminal' in line.lower()
        
        # Only consider movable macros (not standard cells, not fixed)
        # Macros typically have larger area than standard cells
        area = width * height
        if not is_terminal and area > 1000:  # threshold for macro vs standard cell
            macros.append(node_name)
            macro_info[node_name] = {
                'width': width,
                'height': height,
                'area': area
            }
    
    return macros, macro_info


def parse_nets_file(nets_file, macros_set):
    """Parse .nets file to build connectivity graph for macros."""
    G = nx.Graph()
    macro_connections = defaultdict(set)
    
    # Add all macro nodes
    for macro in macros_set:
        G.add_node(macro)
    
    with open(nets_file, 'r') as f:
        lines = f.readlines()
    
    # Skip header
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('NumNets'):
            start_idx = i + 1
            break
    
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            i += 1
            continue
        
        # Check if this is a net definition
        if line.startswith('NetDegree'):
            parts = line.split()
            net_degree = int(parts[2])
            
            # Parse nodes in this net
            net_nodes = []
            for j in range(1, net_degree + 1):
                if i + j >= len(lines):
                    break
                node_line = lines[i + j].strip()
                if node_line and not node_line.startswith('#'):
                    node_name = node_line.split()[0]
                    if node_name in macros_set:
                        net_nodes.append(node_name)
            
            # Add edges between all macros in this net
            for idx1, node1 in enumerate(net_nodes):
                for node2 in net_nodes[idx1 + 1:]:
                    if not G.has_edge(node1, node2):
                        G.add_edge(node1, node2, weight=1)
                    else:
                        G[node1][node2]['weight'] += 1
            
            i += net_degree + 1
        else:
            i += 1
    
    return G


def compute_pagerank(G, alpha=0.85, max_iter=100):
    """Compute PageRank centrality."""
    try:
        pagerank_scores = nx.pagerank(G, alpha=alpha, max_iter=max_iter, weight='weight')
        return pagerank_scores
    except Exception as e:
        print(f"Warning: PageRank computation failed: {e}")
        # Return uniform scores
        return {node: 1.0 / len(G.nodes()) for node in G.nodes()}


def compute_eigenvector_centrality(G, max_iter=100):
    """Compute Eigenvector Centrality."""
    try:
        evc_scores = nx.eigenvector_centrality(G, max_iter=max_iter, weight='weight')
        return evc_scores
    except Exception as e:
        print(f"Warning: Eigenvector centrality computation failed: {e}")
        # Fall back to degree centrality
        return nx.degree_centrality(G)


def compute_betweenness_centrality(G):
    """Compute Betweenness Centrality."""
    try:
        bc_scores = nx.betweenness_centrality(G, weight='weight')
        return bc_scores
    except Exception as e:
        print(f"Warning: Betweenness centrality computation failed: {e}")
        return {node: 0.0 for node in G.nodes()}


def compute_closeness_centrality(G):
    """Compute Closeness Centrality."""
    try:
        cc_scores = nx.closeness_centrality(G, distance='weight')
        return cc_scores
    except Exception as e:
        print(f"Warning: Closeness centrality computation failed: {e}")
        return {node: 0.0 for node in G.nodes()}


def compute_degree_centrality(G):
    """Compute Degree Centrality."""
    return nx.degree_centrality(G)


def compute_all_centralities(nodes_file, nets_file, output_file=None):
    """Compute all centrality metrics and save to pickle file."""
    
    print(f"Parsing nodes file: {nodes_file}")
    macros, macro_info = parse_nodes_file(nodes_file)
    print(f"Found {len(macros)} movable macros")
    
    print(f"Parsing nets file: {nets_file}")
    macros_set = set(macros)
    G = parse_nets_file(nets_file, macros_set)
    print(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    
    # Compute three main centrality metrics
    print("Computing PageRank...")
    pagerank = compute_pagerank(G)
    
    print("Computing Eigenvector Centrality...")
    eigenvector = compute_eigenvector_centrality(G)
    
    print("Computing Degree Centrality...")
    degree = compute_degree_centrality(G)
    
    # Prepare result dictionary
    results = {
        'macros': macros,
        'macro_info': macro_info,
        'graph': G,
        'centralities': {
            'pagerank': pagerank,
            'eigenvector': eigenvector,
            'degree': degree
        }
    }
    
    # Print top 10 macros by each centrality metric
    print("\nTop 10 macros by PageRank:")
    sorted_pr = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
    for i, (node, score) in enumerate(sorted_pr[:10]):
        print(f"  {i+1}. {node}: {score:.6f}")
    
    print("\nTop 10 macros by Eigenvector Centrality:")
    sorted_evc = sorted(eigenvector.items(), key=lambda x: x[1], reverse=True)
    for i, (node, score) in enumerate(sorted_evc[:10]):
        print(f"  {i+1}. {node}: {score:.6f}")
    
    print("\nTop 10 macros by Degree Centrality:")
    sorted_deg = sorted(degree.items(), key=lambda x: x[1], reverse=True)
    for i, (node, score) in enumerate(sorted_deg[:10]):
        print(f"  {i+1}. {node}: {score:.6f}")
    
    # Save to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'wb') as f:
            pickle.dump(results, f)
        print(f"\nCentrality metrics saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Compute centrality metrics for VLSI macro nodes'
    )
    parser.add_argument(
        '--nodes',
        type=str,
        required=True,
        help='Path to .nodes file'
    )
    parser.add_argument(
        '--nets',
        type=str,
        required=True,
        help='Path to .nets file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output pickle file path (optional)'
    )
    
    args = parser.parse_args()
    
    # Auto-generate output filename if not specified
    if args.output is None:
        nodes_path = Path(args.nodes)
        benchmark_name = nodes_path.stem.replace('.nodes', '')
        output_dir = nodes_path.parent
        args.output = str(output_dir / f'{benchmark_name}_centrality.pkl')
    
    compute_all_centralities(args.nodes, args.nets, args.output)


if __name__ == '__main__':
    main()
