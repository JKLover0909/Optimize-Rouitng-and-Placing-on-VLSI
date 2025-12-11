#!/usr/bin/env python3
"""
DREAMPlace GUI - Streamlit Interface
A complete workflow for IC placement optimization with PageRank and Routing
"""

import streamlit as st
import subprocess
import os
import glob
from pathlib import Path
import shutil
from PIL import Image
import re
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

# Configuration
THESIS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = "DREAMPlace/install"
BENCHMARKS_DIR = f"{BASE_DIR}/benchmarks/ispd2005"
RESULTS_DIR = f"{BASE_DIR}/results"
ROUTING_RESULTS_DIR = "routing_results"
SCRIPTS_DIR = "."
NTHU_ROUTE_DIR = "nthu-route/nthuRouter3"
NTHU_ROUTE_BINARY = os.path.join(THESIS_DIR, NTHU_ROUTE_DIR, "NthuRoute")

# Routing converter parameters (fixed)
TILE_SIZE = 35
ADJUSTMENT_FACTOR = 50
SAFE_GUARD_FACTOR = 90
ROUTING_MODE = 2  # 2 layers

# NthuRoute parameters (fixed)
NTHU_PARAMS = {
    "p2_max_iteration": 150,
    "p2_init_box_size": 25,
    "p2_box_expand_size": 1,
    "overflow_threshold": 0,
    "p3_max_iteration": 20,
    "p3_init_box_size": 10,
    "p3_box_expand_size": 15,
    "monotonic_routing": 0
}

# Page configuration
st.set_page_config(
    page_title="DREAMPlace + PageRank Optimizer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        font-size: 1.8rem;
        font-weight: bold;
        color: #2ca02c;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'selected_benchmark' not in st.session_state:
    st.session_state.selected_benchmark = None
if 'selected_pagerank' not in st.session_state:
    st.session_state.selected_pagerank = None
if 'component_type' not in st.session_state:
    st.session_state.component_type = None  # "global", "macro", "stdcell"
if 'placement_status' not in st.session_state:
    st.session_state.placement_status = None  # "movable", "fixed"
if 'pagerank_completed' not in st.session_state:
    st.session_state.pagerank_completed = False
if 'dreamplace_completed' not in st.session_state:
    st.session_state.dreamplace_completed = False
if 'routing_input_file' not in st.session_state:
    st.session_state.routing_input_file = None
if 'routing_output_dir' not in st.session_state:
    st.session_state.routing_output_dir = None
if 'routing_completed' not in st.session_state:
    st.session_state.routing_completed = False
if 'convert_completed' not in st.session_state:
    st.session_state.convert_completed = False

def get_available_benchmarks():
    """Scan and return all available benchmarks in ispd2005 folder."""
    if not os.path.exists(BENCHMARKS_DIR):
        return []
    
    benchmarks = []
    for item in os.listdir(BENCHMARKS_DIR):
        benchmark_path = os.path.join(BENCHMARKS_DIR, item)
        if os.path.isdir(benchmark_path):
            # Check if it has required files
            nodes_file = os.path.join(benchmark_path, f"{item}.nodes")
            nets_file = os.path.join(benchmark_path, f"{item}.nets")
            pl_file = os.path.join(benchmark_path, f"{item}.pl")
            
            if os.path.exists(nodes_file) and os.path.exists(nets_file) and os.path.exists(pl_file):
                benchmarks.append(item)
    
    return sorted(benchmarks)

def backup_original_pl(benchmark):
    """Backup original .pl file if not already backed up."""
    pl_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.pl"
    backup_file = f"{pl_file}.original"
    
    if not os.path.exists(backup_file) and os.path.exists(pl_file):
        shutil.copy2(pl_file, backup_file)
        return True
    return False

def restore_original_pl(benchmark):
    """Restore original .pl file from backup."""
    pl_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.pl"
    backup_file = f"{pl_file}.original"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, pl_file)
        return True
    return False

def run_pagerank_script(benchmark, component_type, placement_status, output_container=None):
    """Run PageRank script using the combined script."""
    script_path = f"{SCRIPTS_DIR}/makePL_combined.py"
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    
    try:
        # Restore original .pl before running PageRank
        restore_original_pl(benchmark)
        
        # Build command with component_type and placement_status
        # For global, placement_status should be "all"
        status = "all" if component_type == "global" else placement_status
        cmd = ['python3', script_path, benchmark, component_type, status]
        
        # Run with real-time output
        process = subprocess.Popen(
            cmd,
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Collect output
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:
            output_lines.append(line)
            if output_container:
                log_placeholder.code(''.join(output_lines), language='text')
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            return True, full_output
        else:
            return False, full_output
            
    except subprocess.TimeoutExpired:
        return False, "Script execution timeout (>5 minutes)"
    except Exception as e:
        return False, str(e)

def run_dreamplace(benchmark, output_container=None):
    """Run DREAMPlace using the run_dreamplace.sh script."""
    script_path = f"{SCRIPTS_DIR}/run_dreamplace.sh"
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    
    try:
        # Run with real-time output
        process = subprocess.Popen(
            ['bash', script_path, benchmark],
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Collect output
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:
            output_lines.append(line)
            if output_container:
                # Show last 100 lines to avoid overflow
                display_lines = output_lines[-100:]
                log_placeholder.code(''.join(display_lines), language='text')
        
        process.wait()
        full_output = ''.join(output_lines)
        
        # Save log to file (ignore permission errors)
        try:
            log_file = f"{RESULTS_DIR}/{benchmark}/placement.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, 'w') as f:
                f.write(full_output)
        except (PermissionError, OSError) as e:
            # Log exists but can't write - will try to read it anyway
            pass
        
        if process.returncode == 0:
            return True, full_output
        else:
            return False, full_output
            
    except subprocess.TimeoutExpired:
        return False, "DREAMPlace execution timeout (>10 minutes)"
    except Exception as e:
        return False, str(e)

def rotate_image_180(image_path):
    """Flip image vertically (top-bottom)."""
    try:
        img = Image.open(image_path)
        # Flip vertical only (top-bottom)
        final_img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return final_img
    except Exception as e:
        st.error(f"Error rotating image: {e}")
        return Image.open(image_path)

def parse_dreamplace_log(log_path):
    """Parse DREAMPlace log file to extract metrics."""
    if not os.path.exists(log_path):
        return None
    
    iterations = []
    hpwls = []
    overflows = []
    times = []
    total_runtime = None
    
    try:
        with open(log_path, 'r') as f:
            for line in f:
                # Parse iteration metrics
                # Format: iteration 404, ( 404,  0,  0), Obj 4.291653E+07, DensityWeight 4.309693E-05, wHPWL 7.124266E+07, Overflow 5.932706E-01
                match = re.search(r'iteration\s+(\d+),.*wHPWL\s+([0-9.E+\-]+).*Overflow\s+([0-9.E+\-]+)', line)
                if match:
                    iter_num = int(match.group(1))
                    hpwl = float(match.group(2))
                    overflow = float(match.group(3))
                    iterations.append(iter_num)
                    hpwls.append(hpwl)
                    overflows.append(overflow * 100)  # Convert to percentage
                
                # Parse total runtime
                # Format: DREAMPlace - placement takes 40.393 seconds
                if 'placement takes' in line:
                    runtime_match = re.search(r'placement takes\s+([0-9.]+)\s+seconds', line)
                    if runtime_match:
                        total_runtime = float(runtime_match.group(1))
        
        if not iterations:
            return None
        
        return {
            'iterations': iterations,
            'hpwls': hpwls,
            'overflows': overflows,
            'final_hpwl': hpwls[-1] if hpwls else None,
            'final_overflow': overflows[-1] if overflows else None,
            'total_runtime': total_runtime,
            'total_iterations': iterations[-1] if iterations else 0
        }
    except Exception as e:
        st.error(f"Error parsing log: {e}")
        return None

def get_latest_plot_image(benchmark):
    """Find and return path to the latest iteration plot image."""
    plot_dir = f"{RESULTS_DIR}/{benchmark}/plot"
    
    if not os.path.exists(plot_dir):
        return None
    
    # Find all iter*.png files
    png_files = glob.glob(f"{plot_dir}/iter*.png")
    
    if not png_files:
        return None
    
    # Extract iteration numbers and find max
    def get_iter_number(filepath):
        filename = os.path.basename(filepath)
        # Extract number from iter0001.png -> 1
        try:
            num_str = filename.replace('iter', '').replace('.png', '')
            return int(num_str)
        except:
            return -1
    
    latest_file = max(png_files, key=get_iter_number)
    return latest_file

def reset_workflow():
    """Reset the entire workflow to start over."""
    st.session_state.step = 1
    st.session_state.selected_benchmark = None
    st.session_state.selected_pagerank = None
    st.session_state.component_type = None
    st.session_state.placement_status = None
    st.session_state.pagerank_completed = False
    st.session_state.dreamplace_completed = False
    st.session_state.routing_input_file = None
    st.session_state.routing_output_dir = None
    st.session_state.routing_completed = False
    st.session_state.convert_completed = False


def get_routing_output_dir_name():
    """Generate routing output directory name based on current settings."""
    benchmark = st.session_state.selected_benchmark
    comp_type = st.session_state.component_type or "global"
    placement = st.session_state.placement_status or "all"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{benchmark}_{comp_type}_{placement}_{timestamp}"


def run_placement_to_routing_converter(benchmark, output_dir, output_container=None):
    """Convert placement result to routing input (.gr file)."""
    
    # Import the converter
    from Placement_to_routing_converter import RoutingBenchmarkGenerator
    
    # File paths
    nodes_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.nodes"
    nets_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.nets"
    scl_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.scl"
    solution_file = f"{RESULTS_DIR}/{benchmark}/{benchmark}.gp.pl"
    
    # Output .gr file name: {benchmark}.3d.{tile}.{adj}.{safe}.gr
    gr_filename = f"{benchmark}.3d.{TILE_SIZE}.{ADJUSTMENT_FACTOR}.{SAFE_GUARD_FACTOR}.gr"
    output_file = f"{output_dir}/{gr_filename}"
    
    try:
        generator = RoutingBenchmarkGenerator()
        
        if output_container:
            output_container.write("Phase 0: Processing SCL file...")
        if not generator.process_scl_file(scl_file):
            return False, "SCL file processing failed", None
        
        if output_container:
            output_container.write("Phase 1: Processing nodes file...")
        if not generator.process_node_file(nodes_file):
            return False, "Nodes file processing failed", None
        
        if output_container:
            output_container.write("Phase 2: Processing solution file...")
        if not generator.process_solution_file(solution_file):
            return False, "Solution file processing failed", None
        
        if output_container:
            output_container.write("Phase 3: Processing nets file...")
        pin_bounds = generator.process_net_file(nets_file)
        if not pin_bounds:
            return False, "Nets file processing failed", None
        
        if output_container:
            output_container.write("Phase 4: Generating routing benchmark...")
        if not generator.generate_benchmark(output_file, TILE_SIZE, ADJUSTMENT_FACTOR, 
                                            SAFE_GUARD_FACTOR, ROUTING_MODE, pin_bounds):
            return False, "Benchmark generation failed", None
        
        if output_container:
            output_container.write(f"✅ Routing input generated: {gr_filename}")
        
        return True, "Conversion completed successfully", output_file
        
    except Exception as e:
        return False, str(e), None


def run_nthu_route(input_gr_file, output_dir, output_container=None):
    """Run NTHU-Route global router."""
    
    nthu_route_exe = os.path.join(THESIS_DIR, NTHU_ROUTE_DIR, "NthuRoute")
    # FLUTE data files are in parent directory (nthu-route/), not nthuRouter3/
    nthu_route_cwd = os.path.join(THESIS_DIR, "nthu-route")  # FLUTE needs POWV9.dat and POST9.dat in cwd
    output_file = f"{output_dir}/output"
    
    if not os.path.exists(nthu_route_exe):
        return False, f"NthuRoute executable not found: {nthu_route_exe}", {}
    
    # Check for required FLUTE data files
    powv_file = os.path.join(nthu_route_cwd, "POWV9.dat")
    post_file = os.path.join(nthu_route_cwd, "POST9.dat")
    if not os.path.exists(powv_file) or not os.path.exists(post_file):
        return False, f"FLUTE data files (POWV9.dat, POST9.dat) not found in {nthu_route_cwd}", {}
    
    # Build command
    cmd = [
        nthu_route_exe,
        f"--input={input_gr_file}",
        f"--output={output_file}",
        f"--p2-max-iteration={NTHU_PARAMS['p2_max_iteration']}",
        f"--p2-init-box-size={NTHU_PARAMS['p2_init_box_size']}",
        f"--p2-box-expand-size={NTHU_PARAMS['p2_box_expand_size']}",
        f"--overflow-threshold={NTHU_PARAMS['overflow_threshold']}",
        f"--p3-max-iteration={NTHU_PARAMS['p3_max_iteration']}",
        f"--p3-init-box-size={NTHU_PARAMS['p3_init_box_size']}",
        f"--p3-box-expand-size={NTHU_PARAMS['p3_box_expand_size']}",
        f"--monotonic-routing={NTHU_PARAMS['monotonic_routing']}"
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=nthu_route_cwd,  # Must run from NthuRoute directory for FLUTE data files
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_lines = []
        metrics = {
            'wirelength': None,
            'overflow': None,
            'runtime': None
        }
        
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:
            output_lines.append(line)
            if output_container:
                # Show last 50 lines
                display_lines = output_lines[-50:]
                log_placeholder.code(''.join(display_lines), language='text')
            
            # Parse metrics from output
            if 'total wire length:' in line.lower():
                match = re.search(r'total wire length:\s*(\d+)', line, re.IGNORECASE)
                if match:
                    metrics['wirelength'] = int(match.group(1))
            
            if 'max overflow=' in line.lower():
                match = re.search(r'max overflow=\s*(\d+)', line, re.IGNORECASE)
                if match:
                    metrics['overflow'] = int(match.group(1))
            
            if 'Total time:' in line:
                match = re.search(r'Total time:\s*([\d.]+)\s*seconds', line)
                if match:
                    metrics['runtime'] = float(match.group(1))
            
            if 'Routing completed in' in line:
                match = re.search(r'Routing completed in\s*([\d.]+)\s*seconds', line)
                if match:
                    metrics['runtime'] = float(match.group(1))
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            return True, full_output, metrics
        else:
            return False, full_output, metrics
            
    except Exception as e:
        return False, str(e), {}


def run_routing_visualization(routing_output_file, output_dir, output_container=None):
    """Run visualization script on routing output."""
    
    visualize_script = f"{SCRIPTS_DIR}/visualize_routing.py"
    
    if not os.path.exists(visualize_script):
        return False, f"Visualization script not found: {visualize_script}"
    
    cmd = [
        'python3', visualize_script,
        '--input', routing_output_file,
        '--output-dir', output_dir
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:
            output_lines.append(line)
            if output_container:
                log_placeholder.code(''.join(output_lines), language='text')
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            return True, full_output
        else:
            return False, full_output
            
    except Exception as e:
        return False, str(e)

# Main App
def main():
    # Header
    st.markdown('<div class="main-header">🔬 DREAMPlace + PageRank + Routing</div>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    with st.sidebar:
        st.header("📋 Workflow Progress")
        
        # Progress indicators - Placement Phase
        st.subheader("🔧 Placement Phase")
        
        if st.session_state.step >= 1:
            st.success("✅ Step 1: Benchmark Selection")
        else:
            st.info("⏳ Step 1: Benchmark Selection")
        
        if st.session_state.step >= 2:
            st.success("✅ Step 2: Component Type")
        else:
            st.info("⏳ Step 2: Component Type")
        
        # Show step 2.5 only if macro or stdcell is selected
        if st.session_state.component_type in ["macro", "stdcell"]:
            if st.session_state.step >= 2.5:
                st.success("✅ Step 2.5: Placement Status")
            else:
                st.info("⏳ Step 2.5: Placement Status")
        
        if st.session_state.step >= 3:
            st.success("✅ Step 3: Run DREAMPlace")
        else:
            st.info("⏳ Step 3: Run DREAMPlace")
        
        if st.session_state.step >= 4:
            st.success("✅ Step 4: Placement Results")
        else:
            st.info("⏳ Step 4: Placement Results")
        
        # Routing Phase
        st.subheader("🛤️ Routing Phase")
        
        if st.session_state.step >= 5:
            st.success("✅ Step 5: Convert to Routing")
        else:
            st.info("⏳ Step 5: Convert to Routing")
        
        if st.session_state.step >= 6:
            st.success("✅ Step 6: Run NTHU-Route")
        else:
            st.info("⏳ Step 6: Run NTHU-Route")
        
        if st.session_state.routing_completed:
            st.success("✅ Step 7: Routing Results")
        else:
            st.info("⏳ Step 7: Routing Results")
        
        st.markdown("---")
        
        # Display current selections
        if st.session_state.selected_benchmark:
            st.write(f"**Benchmark:** {st.session_state.selected_benchmark}")
        
        if st.session_state.component_type:
            type_labels = {"global": "🌐 Global", "macro": "📦 Macro", "stdcell": "📱 Standard Cells"}
            st.write(f"**Type:** {type_labels.get(st.session_state.component_type, st.session_state.component_type)}")
        
        if st.session_state.placement_status:
            status_labels = {"movable": "🔄 Movable", "fixed": "📌 Fixed"}
            st.write(f"**Status:** {status_labels.get(st.session_state.placement_status, st.session_state.placement_status)}")
        
        if st.session_state.routing_output_dir:
            st.write(f"**Output:** {os.path.basename(st.session_state.routing_output_dir)}")
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Reset Workflow", type="secondary"):
            reset_workflow()
            st.rerun()
    
    # Main content
    if st.session_state.step == 1:
        show_step1_benchmark_selection()
    elif st.session_state.step == 2:
        show_step2_component_type()
    elif st.session_state.step == 2.5:
        show_step2_5_placement_status()
    elif st.session_state.step == 3:
        show_step3_run_dreamplace()
    elif st.session_state.step == 4:
        show_step4_view_results()
    elif st.session_state.step == 5:
        show_step5_convert_to_routing()
    elif st.session_state.step == 6:
        show_step6_run_routing()
    elif st.session_state.step == 7:
        show_step7_view_routing_results()

def show_step1_benchmark_selection():
    """Step 1: Select benchmark from ISPD2005."""
    st.markdown('<div class="step-header">Step 1: Select Benchmark (ISPD2005)</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">Select a benchmark from the ISPD2005 suite to begin the optimization workflow.</div>', unsafe_allow_html=True)
    
    # Get available benchmarks
    benchmarks = get_available_benchmarks()
    
    if not benchmarks:
        st.error("❌ No benchmarks found in the ISPD2005 directory!")
        st.write(f"Expected location: `{BENCHMARKS_DIR}`")
        return
    
    st.write(f"**Found {len(benchmarks)} benchmarks:**")
    
    # Create columns for better layout
    cols = st.columns(4)
    
    for idx, benchmark in enumerate(benchmarks):
        col = cols[idx % 4]
        
        with col:
            if st.button(
                benchmark,
                key=f"bench_{benchmark}",
                use_container_width=True,
                type="primary" if st.session_state.selected_benchmark == benchmark else "secondary"
            ):
                st.session_state.selected_benchmark = benchmark
                # Backup original .pl file
                backup_original_pl(benchmark)
    
    # Show selection
    if st.session_state.selected_benchmark:
        st.markdown("---")
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
        
        # Show benchmark info
        benchmark = st.session_state.selected_benchmark
        nodes_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.nodes"
        
        if os.path.exists(nodes_file):
            with open(nodes_file, 'r') as f:
                lines = f.readlines()
                # Find NumNodes line
                for line in lines:
                    if 'NumNodes' in line:
                        st.write(f"📊 {line.strip()}")
                        break
        
        # Next button
        if st.button("➡️ Next: Select Component Type", type="primary"):
            st.session_state.step = 2
            st.rerun()

def show_step2_component_type():
    """Step 2: Select component type for PageRank optimization."""
    st.markdown('<div class="step-header">Step 2: Select Component Type</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Select which type of components to optimize with PageRank:")
    
    st.markdown("""
    <div class="info-box">
    <strong>Component Classification (based on .scl row height):</strong><br>
    • <strong>Standard Cells:</strong> Height ≤ row height (typically 1 row)<br>
    • <strong>Macros:</strong> Height > row height (multi-row blocks)
    </div>
    """, unsafe_allow_html=True)
    
    # Component type options
    component_options = {
        "global": {
            "name": "🌐 Global (All Components)",
            "description": "Sort ALL components by PageRank score regardless of type"
        },
        "macro": {
            "name": "📦 Macro Blocks",
            "description": "Sort only macro blocks (height > row height)"
        },
        "stdcell": {
            "name": "📱 Standard Cells",
            "description": "Sort only standard cells (height ≤ row height)"
        }
    }
    
    # Display options as cards
    for comp_type, option_info in component_options.items():
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**{option_info['name']}**")
                st.caption(option_info['description'])
            
            with col2:
                if st.button(
                    "Select",
                    key=f"comp_{comp_type}",
                    use_container_width=True,
                    type="primary" if st.session_state.component_type == comp_type else "secondary"
                ):
                    st.session_state.component_type = comp_type
                    # If global is selected, clear placement_status
                    if comp_type == "global":
                        st.session_state.placement_status = None
    
    # Show selection and next button
    if st.session_state.component_type:
        st.markdown("---")
        type_labels = {"global": "🌐 Global", "macro": "📦 Macro", "stdcell": "📱 Standard Cells"}
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{type_labels[st.session_state.component_type]}</strong></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Benchmark Selection", type="secondary"):
                st.session_state.step = 1
                st.session_state.component_type = None
                st.session_state.placement_status = None
                st.rerun()
        
        with col2:
            if st.session_state.component_type == "global":
                # Global selected - run PageRank directly
                if st.button("🚀 Run PageRank Optimization", type="primary"):
                    run_pagerank_and_proceed()
            else:
                # Macro or StdCell selected - go to placement status selection
                if st.button("➡️ Next: Select Placement Status", type="primary"):
                    st.session_state.step = 2.5
                    st.rerun()


def show_step2_5_placement_status():
    """Step 2.5: Select placement status (movable or fixed) for non-global options."""
    st.markdown('<div class="step-header">Step 2.5: Select Placement Status</div>', unsafe_allow_html=True)
    
    type_labels = {"macro": "📦 Macro", "stdcell": "📱 Standard Cells"}
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Component Type: <strong>{type_labels[st.session_state.component_type]}</strong></div>', unsafe_allow_html=True)
    
    st.write("Select the placement status of components to optimize:")
    
    st.markdown("""
    <div class="info-box">
    <strong>Placement Status:</strong><br>
    • <strong>Movable:</strong> Components that can be moved during placement optimization<br>
    • <strong>Fixed:</strong> Components with fixed positions (terminals, I/O pads)
    </div>
    """, unsafe_allow_html=True)
    
    # Placement status options
    status_options = {
        "movable": {
            "name": "🔄 Movable Components",
            "description": "Optimize only movable components (non-fixed, non-terminal)"
        },
        "fixed": {
            "name": "📌 Fixed Components",
            "description": "Optimize only fixed/terminal components"
        }
    }
    
    # Display options
    for status, option_info in status_options.items():
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**{option_info['name']}**")
                st.caption(option_info['description'])
            
            with col2:
                if st.button(
                    "Select",
                    key=f"status_{status}",
                    use_container_width=True,
                    type="primary" if st.session_state.placement_status == status else "secondary"
                ):
                    st.session_state.placement_status = status
    
    # Show selection and action buttons
    if st.session_state.placement_status:
        st.markdown("---")
        status_labels = {"movable": "🔄 Movable", "fixed": "📌 Fixed"}
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{status_labels[st.session_state.placement_status]}</strong></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Component Type", type="secondary"):
                st.session_state.step = 2
                st.session_state.placement_status = None
                st.rerun()
        
        with col2:
            if st.button("🚀 Run PageRank Optimization", type="primary"):
                run_pagerank_and_proceed()


def run_pagerank_and_proceed():
    """Run PageRank optimization and proceed to next step."""
    st.info("🔄 Running PageRank optimization...")
    
    # Create container for real-time log
    log_container = st.container()
    with log_container:
        st.subheader("📋 Execution Log")
        log_output = st.empty()
    
    # Determine placement_status
    placement_status = st.session_state.placement_status if st.session_state.placement_status else "all"
    
    success, output = run_pagerank_script(
        st.session_state.selected_benchmark,
        st.session_state.component_type,
        placement_status,
        log_output
    )
    
    if success:
        st.success("✅ PageRank optimization completed!")
        
        # Update selected_pagerank for display in later steps
        type_labels = {"global": "Global", "macro": "Macro", "stdcell": "Standard Cells"}
        status_labels = {"movable": "Movable", "fixed": "Fixed", "all": "All"}
        if st.session_state.component_type == "global":
            st.session_state.selected_pagerank = "Global (All Components)"
        else:
            st.session_state.selected_pagerank = f"{type_labels[st.session_state.component_type]} + {status_labels[placement_status]}"
        
        st.session_state.pagerank_completed = True
        st.session_state.step = 3
        st.rerun()
    else:
        st.error("❌ PageRank optimization failed!")
        st.error(output)


def show_step3_run_dreamplace():
    """Step 3: Run DREAMPlace."""
    st.markdown('<div class="step-header">Step 3: Run DREAMPlace</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>PageRank Mode: <strong>{st.session_state.selected_pagerank}</strong></div>', unsafe_allow_html=True)
    
    st.write("Click the button below to run DREAMPlace with the optimized placement file.")
    
    st.markdown('<div class="warning-box">⚠️ This process may take several minutes depending on the benchmark size.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Go back to the appropriate step
        back_step = 2.5 if st.session_state.component_type in ["macro", "stdcell"] else 2
        if st.button("⬅️ Back to PageRank Settings", type="secondary"):
            st.session_state.step = back_step
            st.rerun()
    
    with col2:
        if st.button("🏃 Run DREAMPlace", type="primary"):
            st.info("🔄 Running DREAMPlace (this may take several minutes)...")
            
            # Create container for real-time log
            log_container = st.container()
            with log_container:
                st.subheader("📋 DREAMPlace Execution Log")
                log_output = st.empty()
            
            success, output = run_dreamplace(st.session_state.selected_benchmark, log_output)
            
            if success:
                st.success("✅ DREAMPlace execution completed!")
                
                st.session_state.dreamplace_completed = True
                st.session_state.step = 4
                
                st.balloons()
                st.rerun()
            else:
                st.error("❌ DREAMPlace execution failed!")
                with st.expander("View Error Details"):
                    st.code(output, language="text")

def show_step4_view_results():
    """Step 4: View results and visualization."""
    st.markdown('<div class="step-header">Step 4: Results & Visualization</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="success-box">✅ Optimization completed for <strong>{st.session_state.selected_benchmark}</strong> with <strong>{st.session_state.selected_pagerank}</strong></div>', unsafe_allow_html=True)
    
    # Parse and display metrics
    log_file = f"{RESULTS_DIR}/{st.session_state.selected_benchmark}/placement.log"
    metrics = parse_dreamplace_log(log_file)
    
    if metrics:
        st.markdown("---")
        st.subheader("📊 Placement Metrics")
        
        # Metrics cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            hpwl_m = metrics['final_hpwl'] / 1e6
            st.metric("Final HPWL", f"{hpwl_m:.2f}M")
        
        with col2:
            st.metric("Final Overflow", f"{metrics['final_overflow']:.2f}%")
        
        with col3:
            st.metric("Runtime", f"{metrics['total_runtime']:.2f}s" if metrics['total_runtime'] else "N/A")
        
        with col4:
            st.metric("Iterations", f"{metrics['total_iterations']}")
        
        # HPWL Convergence Chart
        st.markdown("---")
        st.subheader("📈 HPWL Convergence")
        
        if len(metrics['iterations']) > 0:
            fig, ax = plt.subplots(figsize=(12, 5))
            
            # Convert HPWL to millions for readability
            hpwls_m = [h / 1e6 for h in metrics['hpwls']]
            
            ax.plot(metrics['iterations'], hpwls_m, linewidth=2, color='#1f77b4')
            ax.set_xlabel('Iteration', fontsize=12)
            ax.set_ylabel('HPWL (Millions)', fontsize=12)
            ax.set_title('Half-Perimeter Wire Length Convergence', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Mark key milestones if available
            if metrics['total_iterations'] > 600:  # Has legalization phase
                ax.axvline(x=609, color='red', linestyle='--', alpha=0.7, label='Legalization')
                ax.legend()
            
            st.pyplot(fig)
            plt.close()
            
            # Show improvement percentage
            if len(metrics['hpwls']) > 1:
                initial_hpwl = metrics['hpwls'][0]
                final_hpwl = metrics['hpwls'][-1]
                improvement = ((initial_hpwl - final_hpwl) / initial_hpwl) * 100
                st.info(f"💡 HPWL improved by {improvement:.2f}% (from {initial_hpwl/1e6:.2f}M to {final_hpwl/1e6:.2f}M)")
    
    st.markdown("---")
    
    # Get latest plot image
    latest_image = get_latest_plot_image(st.session_state.selected_benchmark)
    
    if latest_image:
        st.subheader("📊 Final Placement Visualization")
        
        # Display image (rotated 180 degrees)
        rotated_img = rotate_image_180(latest_image)
        st.image(rotated_img, caption=f"Final placement: {os.path.basename(latest_image)}", use_column_width=True)
        
        # Show image path
        st.info(f"📁 Full path: `{latest_image}`")
        
        # Results directory info
        results_path = f"{RESULTS_DIR}/{st.session_state.selected_benchmark}"
        st.write(f"**Results directory:** `{results_path}`")
        
        # List all plots
        plot_dir = f"{results_path}/plot"
        if os.path.exists(plot_dir):
            png_files = sorted(glob.glob(f"{plot_dir}/iter*.png"))
            st.write(f"**Total iterations:** {len(png_files)}")
            
            with st.expander(f"View all {len(png_files)} iteration plots"):
                # Show in grid
                cols_per_row = 4
                for i in range(0, len(png_files), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, col in enumerate(cols):
                        idx = i + j
                        if idx < len(png_files):
                            with col:
                                rotated_img = rotate_image_180(png_files[idx])
                                st.image(rotated_img, caption=os.path.basename(png_files[idx]), use_column_width=True)
    else:
        st.warning("⚠️ No visualization found. The plot directory may be empty.")
        st.write(f"Expected location: `{RESULTS_DIR}/{st.session_state.selected_benchmark}/plot`")
    
    st.markdown("---")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Start New Optimization", type="primary", use_container_width=True):
            reset_workflow()
            st.rerun()
    
    with col2:
        if st.button("📥 Download Results", type="secondary", use_container_width=True):
            st.info("Results are saved in the DREAMPlace results directory")
            st.code(f"{RESULTS_DIR}/{st.session_state.selected_benchmark}")
    
    with col3:
        if st.button("➡️ Continue to Routing", type="secondary", use_container_width=True):
            st.session_state.step = 5
            st.rerun()


def show_step5_convert_to_routing():
    """Step 5: Convert placement to routing format"""
    st.header("Step 5: Convert Placement to Routing Format")
    
    benchmark = st.session_state.selected_benchmark
    component_type = st.session_state.get("component_type", "global")
    placement_status = st.session_state.get("placement_status", "all")
    
    st.info(f"""
    **Benchmark:** {benchmark}
    **Component Type:** {component_type}
    **Placement Status:** {placement_status}
    """)
    
    # Create output folder with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder_name = f"{benchmark}_{component_type}_{placement_status}_{timestamp}"
    output_folder = os.path.join(THESIS_DIR, ROUTING_RESULTS_DIR, output_folder_name)
    
    st.write(f"**Output folder:** `{output_folder}`")
    
    # Parameters display
    st.subheader("Conversion Parameters")
    st.write("""
    - **tile_size:** 35
    - **adjustment_factor:** 50
    - **safe_guard:** 90
    """)
    
    # Find the placement file
    pl_file = os.path.join(RESULTS_DIR, benchmark, f"{benchmark}_best.gp.pl")
    if not os.path.exists(pl_file):
        # Try alternative path
        pl_file = os.path.join(RESULTS_DIR, benchmark, f"{benchmark}.gp.pl")
    
    if not os.path.exists(pl_file):
        st.error(f"Placement file not found. Expected: {pl_file}")
        if st.button("⬅️ Back to Results"):
            st.session_state.step = 4
            st.rerun()
        return
    
    st.success(f"Found placement file: `{pl_file}`")
    
    if st.button("🔄 Run Conversion", type="primary", use_container_width=True):
        progress_container = st.empty()
        
        with st.spinner("Converting placement to routing format..."):
            # Create output directory
            os.makedirs(output_folder, exist_ok=True)
            st.session_state.routing_output_folder = output_folder
            
            # The converter function takes (benchmark, output_dir, output_container)
            success, message, output_file = run_placement_to_routing_converter(benchmark, output_folder, progress_container)
            
            if success:
                st.success("✅ Conversion completed successfully!")
                st.code(message, language="text")
                st.session_state.convert_completed = True
                
                # Check for generated .gr file
                gr_file = os.path.join(output_folder, f"{benchmark}.3d.{TILE_SIZE}.{ADJUSTMENT_FACTOR}.{SAFE_GUARD_FACTOR}.gr")
                if os.path.exists(gr_file):
                    st.success(f"Generated routing file: `{gr_file}`")
                elif output_file and os.path.exists(output_file):
                    st.success(f"Generated routing file: `{output_file}`")
            else:
                st.error("❌ Conversion failed!")
                st.code(message, language="text")
    
    # Navigation
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("⬅️ Back to Results", use_container_width=True):
            st.session_state.step = 4
            st.rerun()
    
    with col2:
        if st.session_state.get("convert_completed", False):
            if st.button("➡️ Run Routing", type="primary", use_container_width=True):
                st.session_state.step = 6
                st.rerun()


def show_step6_run_routing():
    """Step 6: Run NthuRoute global routing"""
    st.header("Step 6: Run Global Routing (NthuRoute)")
    
    benchmark = st.session_state.selected_benchmark
    output_folder = st.session_state.get("routing_output_folder", "")
    
    if not output_folder or not os.path.exists(output_folder):
        st.error("Routing output folder not found. Please run conversion first.")
        if st.button("⬅️ Back to Conversion"):
            st.session_state.step = 5
            st.rerun()
        return
    
    gr_file = os.path.join(output_folder, f"{benchmark}.3d.{TILE_SIZE}.{ADJUSTMENT_FACTOR}.{SAFE_GUARD_FACTOR}.gr")
    
    if not os.path.exists(gr_file):
        st.error(f"Routing input file not found: {gr_file}")
        if st.button("⬅️ Back to Conversion"):
            st.session_state.step = 5
            st.rerun()
        return
    
    st.info(f"""
    **Benchmark:** {benchmark}
    **Input file:** {gr_file}
    **Output folder:** {output_folder}
    """)
    
    # Display NthuRoute parameters
    st.subheader("NthuRoute Parameters")
    st.code("""
--p2-max-iteration=150
--p2-init-box-size=25
--p2-box-expand-size=1
--overflow-threshold=0
--p3-max-iteration=20
--p3-init-box-size=10
--p3-box-expand-size=15
--monotonic-routing=0
    """, language="text")
    
    if st.button("🚀 Run NthuRoute", type="primary", use_container_width=True):
        progress_placeholder = st.empty()
        log_placeholder = st.empty()
        
        with st.spinner("Running NthuRoute... This may take a while."):
            success, output, metrics = run_nthu_route(gr_file, output_folder, log_placeholder)
            
            if success:
                st.success("✅ Routing completed successfully!")
                
                # Display metrics
                st.subheader("Routing Metrics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Wirelength", metrics.get("wirelength", "N/A"))
                with col2:
                    st.metric("Max Overflow", metrics.get("overflow", "N/A"))
                with col3:
                    st.metric("Runtime", f"{metrics.get('runtime', 'N/A')} s")
                
                # Save metrics to file
                metrics_file = os.path.join(output_folder, "routing_metrics.txt")
                with open(metrics_file, "w") as f:
                    f.write(f"Wirelength: {metrics.get('wirelength', 'N/A')}\n")
                    f.write(f"Max Overflow: {metrics.get('overflow', 'N/A')}\n")
                    f.write(f"Runtime: {metrics.get('runtime', 'N/A')} seconds\n")
                
                st.session_state.routing_completed = True
                st.session_state.routing_metrics = metrics
                
                # Run visualization
                st.subheader("Generating Visualizations...")
                with st.spinner("Creating routing visualizations..."):
                    # Find the routing output file
                    routing_output_file = os.path.join(output_folder, "output")
                    vis_success, vis_output = run_routing_visualization(routing_output_file, output_folder)
                    if vis_success:
                        st.success("✅ Visualizations generated!")
                    else:
                        st.warning(f"Visualization generation had issues: {vis_output}")
            else:
                st.error("❌ Routing failed!")
                
            # Display log output
            with st.expander("View Full Log", expanded=not success):
                st.code(output, language="text")
    
    # Navigation
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("⬅️ Back to Conversion", use_container_width=True):
            st.session_state.step = 5
            st.rerun()
    
    with col2:
        if st.session_state.get("routing_completed", False):
            if st.button("➡️ View Routing Results", type="primary", use_container_width=True):
                st.session_state.step = 7
                st.rerun()


def show_step7_view_routing_results():
    """Step 7: View routing results and visualizations"""
    st.header("Step 7: Routing Results")
    
    benchmark = st.session_state.selected_benchmark
    output_folder = st.session_state.get("routing_output_folder", "")
    
    if not output_folder or not os.path.exists(output_folder):
        st.error("Routing output folder not found.")
        if st.button("⬅️ Back to Start"):
            reset_workflow()
            st.rerun()
        return
    
    # Display summary
    component_type = st.session_state.get("component_type", "global")
    placement_status = st.session_state.get("placement_status", "all")
    
    st.success(f"""
    **Benchmark:** {benchmark}
    **Component Type:** {component_type}
    **Placement Status:** {placement_status}
    **Output Folder:** {output_folder}
    """)
    
    # Display routing metrics
    st.subheader("📊 Routing Metrics")
    metrics = st.session_state.get("routing_metrics", {})
    
    if metrics:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Wirelength", metrics.get("wirelength", "N/A"))
        with col2:
            st.metric("Max Overflow", metrics.get("overflow", "N/A"))
        with col3:
            st.metric("Runtime", f"{metrics.get('runtime', 'N/A')} s")
    else:
        # Try to read from file
        metrics_file = os.path.join(output_folder, "routing_metrics.txt")
        if os.path.exists(metrics_file):
            st.code(open(metrics_file).read(), language="text")
        else:
            st.warning("Metrics not available.")
    
    # Display routing layer images
    st.subheader("🗺️ Routing Layer Visualizations")
    
    # Find all routing layer images
    layer_images = sorted(glob.glob(os.path.join(output_folder, "routing_layer*.png")))
    
    if layer_images:
        # Display in grid
        cols = st.columns(min(3, len(layer_images)))
        for idx, img_path in enumerate(layer_images):
            col_idx = idx % 3
            with cols[col_idx]:
                st.image(img_path, caption=os.path.basename(img_path), use_column_width=True)
    else:
        st.info("No routing layer images found.")
    
    # Display congestion heatmap
    st.subheader("🌡️ Congestion Heatmap")
    heatmap_path = os.path.join(output_folder, "congestion_heatmap.png")
    
    if os.path.exists(heatmap_path):
        st.image(heatmap_path, caption="Congestion Heatmap", use_column_width=True)
    else:
        st.info("Congestion heatmap not found.")
    
    # List all output files
    st.subheader("📁 Output Files")
    if os.path.exists(output_folder):
        files = os.listdir(output_folder)
        if files:
            for f in sorted(files):
                file_path = os.path.join(output_folder, f)
                size = os.path.getsize(file_path)
                st.write(f"- `{f}` ({size:,} bytes)")
        else:
            st.info("No files in output folder.")
    
    # Navigation
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Start New Optimization", type="primary", use_container_width=True):
            reset_workflow()
            st.rerun()
    
    with col2:
        if st.button("⬅️ Back to Routing", use_container_width=True):
            st.session_state.step = 6
            st.rerun()


if __name__ == "__main__":
    main()
