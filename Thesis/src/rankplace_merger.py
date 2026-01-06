#!/usr/bin/env python3
"""
RankPlace Merger - Merge MaskPlace inference output with original placement file

Workflow:
1. Read .pl.original (all nodes with original coordinates)
2. Read .pl from MaskPlace inference (macro nodes with new coordinates)
3. Update macro coordinates in the original placement
4. Write merged .pl file for DREAMPlace
"""

import os
from pathlib import Path


def read_pl_file(filepath):
    """
    Read .pl file and return dict of {node_name: (x, y)}
    Format: node_name\tx\ty
    """
    placements = {}
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    placements[node_name] = (x, y)
                except ValueError:
                    # Skip lines that don't have valid coordinates
                    continue
    
    return placements


def read_pl_file_with_orientation(filepath):
    """
    Read .pl file preserving orientation info (if present)
    Format: node_name\tx\ty\t:\tN/S/E/W/FN/FS/FE/FW
    Returns: {node_name: {'x': x, 'y': y, 'orient': orient}}
    """
    placements = {}
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                node_name = parts[0]
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    
                    # Check for orientation (after ':')
                    orient = None
                    if ':' in line:
                        colon_idx = line.index(':')
                        after_colon = line[colon_idx+1:].strip()
                        if after_colon:
                            orient = after_colon
                    
                    placements[node_name] = {
                        'x': x,
                        'y': y,
                        'orient': orient if orient else 'N'
                    }
                except ValueError:
                    continue
    
    return placements


def merge_placement_files(original_pl_path, maskplace_pl_path, output_pl_path):
    """
    Merge MaskPlace placement with original placement file.
    
    Args:
        original_pl_path: Path to .pl.original (all nodes)
        maskplace_pl_path: Path to MaskPlace inference output .pl (macro nodes only)
        output_pl_path: Path to write merged .pl file
    
    Returns:
        dict with merge summary (num_updated, num_total, etc.)
    """
    
    # Read both files
    print(f"Reading original placement: {original_pl_path}")
    original_placements = read_pl_file_with_orientation(original_pl_path)
    
    print(f"Reading MaskPlace placement: {maskplace_pl_path}")
    maskplace_placements = read_pl_file(maskplace_pl_path)
    
    # Count before merge
    total_nodes = len(original_placements)
    macro_nodes_to_update = len(maskplace_placements)
    
    # Update coordinates from MaskPlace output
    num_updated = 0
    for node_name, (x, y) in maskplace_placements.items():
        if node_name in original_placements:
            original_placements[node_name]['x'] = x
            original_placements[node_name]['y'] = y
            num_updated += 1
        else:
            print(f"Warning: Node {node_name} from MaskPlace not found in original placement")
    
    # Write merged placement
    print(f"Writing merged placement: {output_pl_path}")
    os.makedirs(os.path.dirname(output_pl_path), exist_ok=True)
    
    with open(output_pl_path, 'w') as f:
        # Write header
        f.write("UCLA pl 1.0\n")
        f.write("# Merged placement from RankPlace workflow\n\n")
        
        # Write placements
        for node_name in sorted(original_placements.keys()):
            data = original_placements[node_name]
            x = data['x']
            y = data['y']
            orient = data.get('orient', 'N')
            
            # Format: node_name\tx\ty\t:\torient
            f.write(f"{node_name}\t{x:.4f}\t{y:.4f}\t:\t{orient}\n")
    
    summary = {
        'total_nodes': total_nodes,
        'macro_nodes': macro_nodes_to_update,
        'updated_nodes': num_updated,
        'status': 'success' if num_updated > 0 else 'warning'
    }
    
    print(f"✓ Merge complete: {num_updated}/{macro_nodes_to_update} macros updated")
    
    return summary


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Merge MaskPlace inference with original placement for RankPlace workflow'
    )
    parser.add_argument('--original', required=True, help='Path to .pl.original')
    parser.add_argument('--maskplace', required=True, help='Path to MaskPlace inference .pl')
    parser.add_argument('--output', required=True, help='Path to output merged .pl')
    
    args = parser.parse_args()
    
    summary = merge_placement_files(args.original, args.maskplace, args.output)
    print(f"\nSummary: {summary}")
