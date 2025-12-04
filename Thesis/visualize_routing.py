#!/usr/bin/env python3
"""
NTHU-Route Output Visualization Tool
Parses routing output and creates visual representations
"""

import argparse
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection
import numpy as np
from collections import defaultdict


def parse_routing_output(output_file):
    """
    Parse NTHU-Route output file (ISPD 2008 format)
    Returns: dict {net_name: [(p1, p2), ...]}
    """
    nets = {}
    current_net = None
    current_net_id = None
    
    try:
        with open(output_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # End of net marker
                if line == '!':
                    current_net = None
                    continue
                
                # Net header: "net_name net_id [num_segments]"
                if not line.startswith('('):
                    parts = line.split()
                    if len(parts) >= 2:
                        current_net = parts[0]
                        current_net_id = parts[1]
                        nets[current_net] = {
                            'id': current_net_id,
                            'segments': []
                        }
                
                # Segment: "(x1,y1,z1)-(x2,y2,z2)"
                elif ')-(' in line and current_net:
                    # Parse coordinates
                    try:
                        seg = line.replace('(', '').replace(')', '').split('-')
                        p1 = tuple(map(int, seg[0].split(',')))
                        p2 = tuple(map(int, seg[1].split(',')))
                        nets[current_net]['segments'].append((p1, p2))
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse line: {line}")
                        continue
    
    except FileNotFoundError:
        print(f"Error: Output file not found: {output_file}")
        sys.exit(1)
    
    return nets


def get_grid_bounds(nets):
    """Calculate grid boundaries from all segments"""
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    max_z = 0
    
    for net_data in nets.values():
        for (x1, y1, z1), (x2, y2, z2) in net_data['segments']:
            min_x = min(min_x, x1, x2)
            min_y = min(min_y, y1, y2)
            max_x = max(max_x, x1, x2)
            max_y = max(max_y, y1, y2)
            max_z = max(max_z, z1, z2)
    
    return int(min_x), int(min_y), int(max_x), int(max_y), int(max_z)


def visualize_routing_layer(nets, layer, output_png='routing_layer.png', show_net_names=False):
    """
    Visualize routing on specific layer (optimized with LineCollection)
    """
    print(f"\n[Visualizing Layer {layer}]")
    
    # Get grid bounds
    min_x, min_y, max_x, max_y, max_z = get_grid_bounds(nets)
    
    print(f"  Grid bounds: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(20, 20))
    
    # Generate colors for nets
    colors = plt.cm.tab20(np.linspace(0, 1, min(20, len(nets))))
    color_idx = 0
    
    segment_count = 0
    via_count = 0
    
    # Collect all line segments for batch rendering
    all_lines = []
    all_colors = []
    via_points = []
    via_colors = []
    
    print(f"  Collecting segments...")
    
    for net_name, net_data in nets.items():
        color = colors[color_idx % len(colors)]
        color_idx += 1
        
        for (x1, y1, z1), (x2, y2, z2) in net_data['segments']:
            # Draw horizontal/vertical segments on specified layer
            if z1 == layer and z2 == layer:
                if x1 == x2 or y1 == y2:  # Straight line
                    all_lines.append([(x1, y1), (x2, y2)])
                    all_colors.append(color)
                    segment_count += 1
            
            # Draw vias (layer transitions)
            elif x1 == x2 and y1 == y2 and (z1 == layer or z2 == layer):
                via_points.append([x1, y1])
                via_colors.append(color)
                via_count += 1
    
    print(f"  Rendering {segment_count} segments...")
    
    # Batch render all lines using LineCollection (MUCH faster!)
    if all_lines:
        lc = LineCollection(all_lines, colors=all_colors, linewidths=1.5, 
                           alpha=0.7, capstyle='round')
        ax.add_collection(lc)
    
    # Batch render vias
    if via_points:
        via_points = np.array(via_points)
        ax.scatter(via_points[:, 0], via_points[:, 1], 
                  c=via_colors, s=20, marker='o', 
                  alpha=0.8, edgecolors='black', linewidths=0.5)
    
    print(f"  ✓ Segments drawn: {segment_count}")
    print(f"  ✓ Vias drawn: {via_count}")
    
    # Set axis properties
    ax.set_xlim(min_x - 5, max_x + 5)
    ax.set_ylim(min_y - 5, max_y + 5)
    ax.set_xlabel('X Grid', fontsize=14)
    ax.set_ylabel('Y Grid', fontsize=14)
    ax.set_title(f'Global Routing Visualization - Layer {layer}', fontsize=16, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_aspect('equal')
    
    # Add stats text
    stats_text = f'Nets: {len(nets)} | Segments: {segment_count} | Vias: {via_count}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=12, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved to: {output_png}")


def create_congestion_heatmap(nets, grid_size=None, output_png='congestion_heatmap.png'):
    """
    Create congestion heatmap showing routing density (optimized with numpy vectorization)
    """
    print(f"\n[Creating Congestion Heatmap]")
    
    # Get grid bounds
    min_x, min_y, max_x, max_y, max_z = get_grid_bounds(nets)
    
    if grid_size is None:
        grid_size = (max_x - min_x + 1, max_y - min_y + 1)
    
    print(f"  Heatmap size: {grid_size[0]} x {grid_size[1]}")
    print(f"  Processing {len(nets)} nets...")
    
    # Initialize heatmap
    heatmap = np.zeros((grid_size[1], grid_size[0]), dtype=np.int32)
    
    total_segments = 0
    # Count routing through each grid cell (optimized)
    for net_idx, net_data in enumerate(nets.values()):
        if net_idx % 1000 == 0 and net_idx > 0:
            print(f"    Processed {net_idx}/{len(nets)} nets...")
        
        for (x1, y1, z1), (x2, y2, z2) in net_data['segments']:
            if z1 == z2:  # Horizontal/vertical routing (not via)
                total_segments += 1
                # Draw line between points (vectorized)
                if x1 == x2:  # Vertical line
                    y_start = min(y1, y2)
                    y_end = max(y1, y2)
                    hx = x1 - min_x
                    
                    if 0 <= hx < grid_size[0]:
                        for y in range(y_start, y_end + 1):
                            hy = y - min_y
                            if 0 <= hy < grid_size[1]:
                                heatmap[hy, hx] += 1
                                
                elif y1 == y2:  # Horizontal line
                    x_start = min(x1, x2)
                    x_end = max(x1, x2)
                    hy = y1 - min_y
                    
                    if 0 <= hy < grid_size[1]:
                        for x in range(x_start, x_end + 1):
                            hx = x - min_x
                            if 0 <= hx < grid_size[0]:
                                heatmap[hy, hx] += 1
    
    max_congestion = np.max(heatmap)
    avg_congestion = np.mean(heatmap[heatmap > 0]) if np.any(heatmap > 0) else 0
    print(f"  ✓ Processed {total_segments} segments")
    print(f"  ✓ Max congestion: {int(max_congestion)}, Avg: {avg_congestion:.2f}")
    
    # Create visualization
    fig, ax = plt.subplots(figsize=(16, 14))
    
    im = ax.imshow(heatmap, cmap='hot', interpolation='nearest', aspect='auto')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Congestion Level (# of wires)', fontsize=12)
    
    ax.set_xlabel('X Grid', fontsize=14)
    ax.set_ylabel('Y Grid', fontsize=14)
    ax.set_title('Routing Congestion Heatmap (All Layers)', fontsize=16, fontweight='bold')
    
    # Add stats
    stats_text = f'Max: {int(max_congestion)} | Avg: {heatmap.mean():.2f} | Total Segments: {int(heatmap.sum())}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=12, verticalalignment='top', color='white',
            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved to: {output_png}")


def visualize_3d_overview(nets, output_png='routing_3d_overview.png'):
    """
    Create multi-layer overview visualization (optimized)
    """
    print(f"\n[Creating 3D Overview]")
    
    min_x, min_y, max_x, max_y, max_z = get_grid_bounds(nets)
    
    # Create subplots for each layer
    num_layers = max_z + 1
    fig, axes = plt.subplots(1, num_layers, figsize=(8 * num_layers, 8))
    
    if num_layers == 1:
        axes = [axes]
    
    colors = plt.cm.tab20(np.linspace(0, 1, min(20, len(nets))))
    
    for layer in range(num_layers):
        print(f"  Processing layer {layer}...")
        ax = axes[layer]
        color_idx = 0
        
        all_lines = []
        all_colors = []
        
        for net_name, net_data in nets.items():
            color = colors[color_idx % len(colors)]
            color_idx += 1
            
            for (x1, y1, z1), (x2, y2, z2) in net_data['segments']:
                if z1 == layer and z2 == layer:
                    all_lines.append([(x1, y1), (x2, y2)])
                    all_colors.append(color)
        
        # Batch render
        if all_lines:
            lc = LineCollection(all_lines, colors=all_colors, linewidths=0.8, alpha=0.6)
            ax.add_collection(lc)
        
        ax.set_xlim(min_x - 5, max_x + 5)
        ax.set_ylim(min_y - 5, max_y + 5)
        ax.set_xlabel('X Grid')
        ax.set_ylabel('Y Grid')
        ax.set_title(f'Layer {layer}', fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
    
    plt.suptitle('Multi-Layer Routing Overview', fontsize=18, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved to: {output_png}")


def print_statistics(nets):
    """Print routing statistics"""
    print("\n" + "="*60)
    print("ROUTING STATISTICS")
    print("="*60)
    
    total_segments = sum(len(net_data['segments']) for net_data in nets.values())
    
    # Count vias and wire segments
    vias = 0
    horizontal = 0
    vertical = 0
    
    wirelength = 0
    
    for net_data in nets.values():
        for (x1, y1, z1), (x2, y2, z2) in net_data['segments']:
            if z1 != z2:
                vias += 1
            elif x1 == x2:
                vertical += 1
                wirelength += abs(y2 - y1)
            elif y1 == y2:
                horizontal += 1
                wirelength += abs(x2 - x1)
    
    min_x, min_y, max_x, max_y, max_z = get_grid_bounds(nets)
    
    print(f"Total Nets:           {len(nets)}")
    print(f"Total Segments:       {total_segments}")
    print(f"  - Horizontal:       {horizontal}")
    print(f"  - Vertical:         {vertical}")
    print(f"  - Vias:             {vias}")
    print(f"Total Wirelength:     {wirelength}")
    print(f"Grid Size:            {max_x - min_x + 1} x {max_y - min_y + 1}")
    print(f"Number of Layers:     {max_z + 1}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Visualize NTHU-Route output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input output
  %(prog)s --input output --layers 1 2 3
  %(prog)s --input output --heatmap-only
  %(prog)s --input output --output-dir ./visualizations
        """
    )
    
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to NTHU-Route output file'
    )
    
    parser.add_argument(
        '--layers',
        type=int,
        nargs='+',
        default=None,
        help='Specific layers to visualize (e.g., --layers 1 2 3). Default: all layers'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Output directory for visualization files (default: current directory)'
    )
    
    parser.add_argument(
        '--heatmap-only',
        action='store_true',
        help='Only generate congestion heatmap'
    )
    
    parser.add_argument(
        '--grid-size',
        type=str,
        default=None,
        help='Grid size for heatmap (e.g., "512,512"). Default: auto-detect'
    )
    
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only print statistics without generating visualizations'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse routing output
    print("="*60)
    print("NTHU-ROUTE VISUALIZATION TOOL")
    print("="*60)
    print(f"\nParsing routing output: {args.input}")
    
    nets = parse_routing_output(args.input)
    
    if not nets:
        print("Error: No nets found in output file")
        sys.exit(1)
    
    print(f"Successfully parsed {len(nets)} nets")
    
    # Print statistics
    print_statistics(nets)
    
    if args.stats_only:
        return
    
    # Parse grid size if provided
    grid_size = None
    if args.grid_size:
        try:
            grid_size = tuple(map(int, args.grid_size.split(',')))
        except ValueError:
            print(f"Warning: Invalid grid size '{args.grid_size}'. Using auto-detect.")
    
    # Generate visualizations
    min_x, min_y, max_x, max_y, max_z = get_grid_bounds(nets)
    
    if args.heatmap_only:
        # Only generate heatmap
        heatmap_file = output_dir / 'congestion_heatmap.png'
        create_congestion_heatmap(nets, grid_size, str(heatmap_file))
    else:
        # Determine which layers to visualize
        if args.layers:
            layers_to_viz = args.layers
        else:
            layers_to_viz = list(range(max_z + 1))
        
        # Visualize each layer
        for layer in layers_to_viz:
            if layer > max_z:
                print(f"Warning: Layer {layer} exceeds max layer {max_z}, skipping")
                continue
            
            layer_file = output_dir / f'routing_layer{layer}.png'
            visualize_routing_layer(nets, layer, str(layer_file))
        
        # Create congestion heatmap
        heatmap_file = output_dir / 'congestion_heatmap.png'
        create_congestion_heatmap(nets, grid_size, str(heatmap_file))
        
        # Create 3D overview
        overview_file = output_dir / 'routing_3d_overview.png'
        visualize_3d_overview(nets, str(overview_file))
    
    print("\n" + "="*60)
    print("✓ Visualization complete!")
    print("="*60)


if __name__ == "__main__":
    main()
