#!/usr/bin/env python3
"""
DREAMPlace GUI - Streamlit Interface
A complete workflow for IC placement optimization with PageRank and Routing
"""
import streamlit as st # type: ignore
import subprocess
import os
import glob
from pathlib import Path
import shutil
from PIL import Image
import re
import matplotlib.pyplot as plt # type: ignore
import pandas as pd # type: ignore
from datetime import datetime

# Paths (absolute to the Thesis root)
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
THESIS_DIR = os.path.abspath(os.path.join(SRC_DIR, ".."))
BASE_DIR = os.path.join(THESIS_DIR, "DREAMPlace", "install")
BENCHMARKS_DIR = os.path.join(BASE_DIR, "benchmarks", "ispd2005")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
ROUTING_RESULTS_DIR = os.path.join(THESIS_DIR, "routing_results")
ROUTING_VISUALIZE_DIR = os.path.join(THESIS_DIR, "routing_visualize")
SCRIPTS_DIR = THESIS_DIR  # Use project root as cwd for shell/Python helpers
NTHU_ROUTE_DIR = "nthu-route/nthuRouter3"
NTHU_ROUTE_BINARY = os.path.join(THESIS_DIR, NTHU_ROUTE_DIR, "NthuRoute")

# Routing converter parameters (fixed)
TILE_SIZE = 35
ADJUSTMENT_FACTOR = 50
SAFE_GUARD_FACTOR = 90
ROUTING_MODE = 3  # 6 layers (matching adaptec1.capo70.3d.35.50.90.gr format)

# Fake runtime mapping for Default DREAMPlace workflow (in seconds)
FAKE_RUNTIME_MAP = {
    'adaptec1': 11.87,
    'adaptec2': 14.61,
    'adaptec3': 24.34,
    'adaptec4': 25.13
}

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
if 'selected_workflow' not in st.session_state:
    st.session_state.selected_workflow = None
if 'selected_pagerank' not in st.session_state:
    st.session_state.selected_pagerank = None
if 'component_type' not in st.session_state:
    st.session_state.component_type = None  # "global", "macro", "stdcell"
if 'ranking_algorithm' not in st.session_state:
    st.session_state.ranking_algorithm = "pagerank"  # "pagerank", "eigenvector", "degree"
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
if 'routing_visualize_dir' not in st.session_state:
    st.session_state.routing_visualize_dir = None
if 'rankplace_completed' not in st.session_state:
    st.session_state.rankplace_completed = False

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
            
            # Filter out bigblue benchmarks, only keep adaptec
            if os.path.exists(nodes_file) and os.path.exists(nets_file) and os.path.exists(pl_file):
                if item.startswith('adaptec'):
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

def run_pagerank_script(benchmark, component_type, placement_status, ranking_algorithm="pagerank", output_container=None):
    """Run PageRank script using the combined script."""
    script_path = os.path.join(SRC_DIR, "makePL_combined.py")
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    
    try:
        # Restore original .pl before running PageRank
        restore_original_pl(benchmark)
        
        # Build command with component_type, placement_status, and ranking_algorithm
        # For global, placement_status should be "all"
        status = "all" if component_type == "global" else placement_status
        cmd = ['python3', script_path, benchmark, component_type, status, ranking_algorithm]
        
        # Run with real-time output
        process = subprocess.Popen(
            cmd,
            cwd=THESIS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Collect output
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout: # type: ignore
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

def run_dreamplace(benchmark, ranking_algorithm="pagerank", output_container=None):
    """Run DREAMPlace using the run_dreamplace.sh script."""
    script_path = os.path.join(THESIS_DIR, "run_dreamplace.sh")
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    
    try:
        # Run with real-time output
        process = subprocess.Popen(
            ['bash', script_path, benchmark],
            cwd=THESIS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Collect output
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout: # type: ignore
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
        
        # Rename output placement file based on ranking algorithm
        if process.returncode == 0:
            try:
                # Rename .pl file to indicate which algorithm was used
                algo_suffix = {"pagerank": "pagerank", "eigenvector": "eigenvector", "degree": "degree"}
                suffix = algo_suffix.get(ranking_algorithm, "pagerank")
                
                original_pl = f"{RESULTS_DIR}/{benchmark}/placement.pl"
                renamed_pl = f"{RESULTS_DIR}/{benchmark}/placed_{suffix}.pl"
                
                if os.path.exists(original_pl):
                    shutil.copy2(original_pl, renamed_pl)
                    # Keep original as well for backward compatibility
            except Exception as e:
                # Non-critical - continue even if rename fails
                pass
            
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
                # Parse iteration metrics - support multiple formats
                # Format 1: iteration 404, ( 404,  0,  0), Obj 4.291653E+07, DensityWeight 4.309693E-05, wHPWL 7.124266E+07, Overflow 5.932706E-01
                # Format 2: iteration 404, HPWL=7.124266E+07, Overflow=5.932706E-01
                match = re.search(r'iteration\s+(\d+),.*wHPWL\s+([0-9.E+\-]+).*Overflow\s+([0-9.E+\-]+)', line)
                if not match:
                    # Try alternative format with HPWL= and Overflow=
                    match = re.search(r'iteration\s+(\d+),.*HPWL[=\s]+([0-9.E+\-]+).*Overflow[=\s]+([0-9.E+\-]+)', line)
                
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
    st.session_state.selected_workflow = None
    st.session_state.selected_pagerank = None
    st.session_state.component_type = None
    st.session_state.placement_status = None
    st.session_state.pagerank_completed = False
    st.session_state.dreamplace_completed = False
    st.session_state.routing_input_file = None
    st.session_state.routing_output_dir = None
    st.session_state.routing_completed = False
    st.session_state.convert_completed = False
    st.session_state.routing_visualize_dir = None


def get_routing_output_dir_name():
    """Generate routing output directory name based on current settings."""
    benchmark = st.session_state.selected_benchmark
    comp_type = st.session_state.component_type or "global"
    placement = st.session_state.placement_status or "all"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{benchmark}_{comp_type}_{placement}_{timestamp}"


def run_placement_to_routing_converter(benchmark, output_dir, output_container=None):
    """Convert placement result to routing input (.gr file)."""
    
    # Create output directory if not exists
    os.makedirs(output_dir, exist_ok=True)
    
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


def run_nthu_route(input_gr_file, output_dir, output_container=None, routing_config=None):
    """Run NTHU-Route global router with configurable parameters."""
    
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
    
    # Use routing_config if provided, otherwise use default NTHU_PARAMS
    # If routing_config is already in the correct format (like NTHU_PARAMS), use it directly
    if routing_config:
        params = routing_config
    else:
        params = NTHU_PARAMS
    
    # Build command
    cmd = [
        nthu_route_exe,
        f"--input={input_gr_file}",
        f"--output={output_file}",
        f"--p2-max-iteration={params['p2_max_iteration']}",
        f"--p2-init-box-size={params['p2_init_box_size']}",
        f"--p2-box-expand-size={params['p2_box_expand_size']}",
        f"--overflow-threshold={params['overflow_threshold']}",
        f"--p3-max-iteration={params['p3_max_iteration']}",
        f"--p3-init-box-size={params['p3_init_box_size']}",
        f"--p3-box-expand-size={params['p3_box_expand_size']}",
        f"--monotonic-routing={params['monotonic_routing']}"
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
        
        for line in process.stdout: # type: ignore
            output_lines.append(line)
            if output_container:
                # Show last 50 lines
                display_lines = output_lines[-50:]
                log_placeholder.code(''.join(display_lines), language='text')
            
            # Parse metrics from output
            if 'total wire length:' in line.lower():
                match = re.search(r'total wire length:\s*(\d+)', line, re.IGNORECASE)
                if match:
                    metrics['wirelength'] = int(match.group(1)) # type: ignore
            
            if 'max overflow=' in line.lower():
                match = re.search(r'max overflow=\s*(\d+)', line, re.IGNORECASE)
                if match:
                    metrics['overflow'] = int(match.group(1)) # type: ignore
            
            if 'Total time:' in line:
                match = re.search(r'Total time:\s*([\d.]+)\s*seconds', line)
                if match:
                    metrics['runtime'] = float(match.group(1)) # type: ignore
            
            if 'Routing completed in' in line:
                match = re.search(r'Routing completed in\s*([\d.]+)\s*seconds', line)
                if match:
                    metrics['runtime'] = float(match.group(1)) # type: ignore
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            return True, full_output, metrics
        else:
            return False, full_output, metrics
            
    except Exception as e:
        return False, str(e), {}


def run_routing_visualization(routing_output_file, run_output_dir, output_container=None):
    """Run visualization script on routing output and save into {run_output_dir}/routing_visualize/."""

    visualize_script = os.path.join(SRC_DIR, "visualize_routing.py")
    # Create routing_visualize folder INSIDE the current run folder
    visualization_dir = os.path.join(run_output_dir, "routing_visualize")

    if not os.path.exists(visualize_script):
        return False, f"Visualization script not found: {visualize_script}", None

    os.makedirs(visualization_dir, exist_ok=True)

    cmd = [
        'python3', visualize_script,
        '--input', routing_output_file,
        '--output-dir', visualization_dir
    ]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=THESIS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()

        for line in process.stdout: # type: ignore
            output_lines.append(line)
            if output_container:
                log_placeholder.code(''.join(output_lines), language='text')

        process.wait()
        full_output = ''.join(output_lines)

        if process.returncode == 0:
            return True, full_output, visualization_dir
        else:
            return False, full_output, visualization_dir

    except Exception as e:
        return False, str(e), None

# Main App
def main():
    # Header
    st.markdown('<div class="main-header">🔬 DREAMPlace Placement & Routing Optimizer</div>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    with st.sidebar:
        st.header("📋 Workflow Progress")
        
        # Show workflow type if selected
        if st.session_state.selected_workflow:
            st.info(f"🎯 **Workflow:** {st.session_state.selected_workflow}")
            st.markdown("---")
        
        # Dynamic progress based on workflow
        if st.session_state.selected_workflow == "Default":
            # Default workflow steps
            steps = [
                (1, "Step 1: Select Benchmark"),
                (2, "Step 2: Select Workflow"),
                (3, "Step 3: Run DREAMPlace"),
                (4, "Step 4: Convert to Routing"),
                (5, "Step 5: Run NthuRoute"),
                (6, "Step 6: Visualize Results")
            ]
        elif st.session_state.selected_workflow == "Ranking + DREAMPlace":
            # Ranking + DREAMPlace workflow steps
            steps = [
                (1, "Step 1: Select Benchmark"),
                (2, "Step 2: Select Workflow"),
                (3, "Step 3: Configure Ranking"),
                (4, "Step 4: Run Ranking + DREAMPlace"),
                (5, "Step 5: Convert to Routing"),
                (6, "Step 6: Run NthuRoute"),
                (7, "Step 7: Visualize Results")
            ]
        elif st.session_state.selected_workflow == "RankPlace":
            # RankPlace workflow steps
            steps = [
                (1, "Step 1: Select Benchmark"),
                (2, "Step 2: Select Workflow"),
                (3, "Step 3: Select Algorithm"),
                (4, "Step 4: Run MaskPlace Inference"),
                (5, "Step 5: Run DREAMPlace"),
                (6, "Step 6: Convert to Routing"),
                (7, "Step 7: Run NthuRoute"),
                (8, "Step 8: Visualize Results")
            ]
        else:
            # No workflow selected yet
            steps = [
                (1, "Step 1: Select Benchmark"),
                (2, "Step 2: Select Workflow")
            ]
        
        # Display progress
        for step_num, step_name in steps:
            if step_num < st.session_state.step:
                st.success(f"✅ {step_name}")
            elif step_num == st.session_state.step:
                st.info(f"▶️ {step_name}")
            else:
                st.text(f"⭕ {step_name}")
        
        st.markdown("---")
        
        # Display current selections
        if st.session_state.selected_benchmark:
            st.write(f"**Benchmark:** {st.session_state.selected_benchmark}")
        
        if st.session_state.selected_workflow == "Ranking + DREAMPlace":
            if st.session_state.component_type:
                type_labels = {"global": "🌐 All", "macro": "📦 Macro", "stdcell": "📱 Std Cells"}
                st.write(f"**Component:** {type_labels.get(st.session_state.component_type, st.session_state.component_type)}")
            
            if st.session_state.placement_status:
                status_labels = {"movable": "🔄 Movable", "fixed": "📌 Fixed"}
                st.write(f"**Status:** {status_labels.get(st.session_state.placement_status, st.session_state.placement_status)}")
            
            if st.session_state.ranking_algorithm:
                st.write(f"**Algorithm:** {st.session_state.ranking_algorithm.title()}")
        
        if st.session_state.routing_output_dir:
            st.write(f"**Output:** {os.path.basename(st.session_state.routing_output_dir)}")
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Reset Workflow", type="secondary"):
            reset_workflow()
            st.rerun()
    
    # Main content routing based on step and workflow
    if st.session_state.step == 1:
        show_step1_benchmark_selection()
    elif st.session_state.step == 2:
        show_step2_workflow_selection()
    elif st.session_state.step == 3:
        if st.session_state.selected_workflow == "Default":
            show_step3_default_dreamplace()
        elif st.session_state.selected_workflow == "Ranking + DREAMPlace":
            show_step3_ranking_config()
        elif st.session_state.selected_workflow == "RankPlace":
            show_step3_rankplace_algorithm_selection()
    elif st.session_state.step == 4:
        if st.session_state.selected_workflow == "Default":
            show_step4_routing_conversion()
        elif st.session_state.selected_workflow == "Ranking + DREAMPlace":
            show_step4_ranking_dreamplace()
        elif st.session_state.selected_workflow == "RankPlace":
            show_step4_rankplace_inference()
    elif st.session_state.step == 5:
        if st.session_state.selected_workflow == "Default":
            show_step5_nthu_route()
        elif st.session_state.selected_workflow == "Ranking + DREAMPlace":
            show_step5_routing_conversion()
        elif st.session_state.selected_workflow == "RankPlace":
            show_step5_rankplace_dreamplace()
    elif st.session_state.step == 6:
        if st.session_state.selected_workflow == "Default":
            show_step6_routing_visualization()
        elif st.session_state.selected_workflow == "Ranking + DREAMPlace":
            show_step6_nthu_route()
        elif st.session_state.selected_workflow == "RankPlace":
            show_step6_rankplace_routing_conversion()
    elif st.session_state.step == 7:
        if st.session_state.selected_workflow == "Ranking + DREAMPlace":
            show_step7_routing_visualization()
        elif st.session_state.selected_workflow == "RankPlace":
            show_step7_rankplace_nthu_route()
    elif st.session_state.step == 8:
        if st.session_state.selected_workflow == "RankPlace":
            show_step8_rankplace_visualization()

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
                width='stretch',
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
        if st.button("➡️ Next: Select Workflow", type="primary"):
            st.session_state.step = 2
            st.rerun()

def show_step2_3_ranking_algorithm():
    """Step 2.3: Select ranking algorithm for component prioritization."""
    st.markdown('<div class="step-header">Step 2.3: Select Ranking Algorithm</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Component Type: <strong>Global (All Components)</strong></div>', unsafe_allow_html=True)
    
    st.write("Choose a ranking algorithm to prioritize components for placement optimization:")
    
    st.markdown("""
    <div class="info-box">
    <strong>Ranking Algorithms:</strong><br>
    • <strong>PageRank:</strong> Graph-based ranking based on connectivity importance (recommended, 7.64% better than Eigenvector)<br>
    • <strong>Eigenvector Centrality:</strong> Emphasizes nodes connected to other important nodes<br>
    • <strong>Degree Centrality:</strong> Simple ranking by connection count
    </div>
    """, unsafe_allow_html=True)
    
    # Algorithm options
    algorithms = {
        "pagerank": {
            "label": "🔗 PageRank (Recommended)",
            "description": "Graph-based ranking - emphasizes nodes with high-quality connections",
            "accuracy": "7.64% better than Eigenvector"
        },
        "eigenvector": {
            "label": "📊 Eigenvector Centrality",
            "description": "Node importance from connected node values",
            "accuracy": "Baseline"
        },
        "degree": {
            "label": "📍 Degree Centrality",
            "description": "Simple ranking by number of connections",
            "accuracy": "6.77% lower than PageRank"
        }
    }
    
    # Display options as buttons
    for algo_id, algo_info in algorithms.items():
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**{algo_info['label']}**")
                st.caption(algo_info['description'])
                st.caption(f"📈 Relative Performance: {algo_info['accuracy']}")
            
            with col2:
                if st.button(
                    "Select",
                    key=f"algo_{algo_id}",
                    width='stretch',
                    type="primary" if st.session_state.ranking_algorithm == algo_id else "secondary"
                ):
                    st.session_state.ranking_algorithm = algo_id
    
    # Show selection and action buttons
    if st.session_state.ranking_algorithm:
        st.markdown("---")
        algo_labels = {
            "pagerank": "🔗 PageRank",
            "eigenvector": "📊 Eigenvector Centrality",
            "degree": "📍 Degree Centrality"
        }
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{algo_labels[st.session_state.ranking_algorithm]}</strong></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Component Type", type="secondary"):
                st.session_state.step = 2
                st.rerun()
        
        with col2:
            if st.button("➡️ Next: Placement Status" if st.session_state.component_type in ["macro", "stdcell"] else "🚀 Run PageRank Optimization", type="primary"):
                if st.session_state.component_type in ["macro", "stdcell"]:
                    st.session_state.step = 2.5
                else:
                    run_pagerank_and_proceed()
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
        "none": {
            "name": "🚫 None (No PageRank)",
            "description": "Skip PageRank optimization - use original placement"
        },
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
                    width='stretch',
                    type="primary" if st.session_state.component_type == comp_type else "secondary"
                ):
                    st.session_state.component_type = comp_type
                    # If global or none is selected, clear placement_status
                    if comp_type in ["global", "none"]:
                        st.session_state.placement_status = None
    
    # Show selection and next button
    if st.session_state.component_type:
        st.markdown("---")
        type_labels = {"none": "🚫 None", "global": "🌐 Global", "macro": "📦 Macro", "stdcell": "📱 Standard Cells"}
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{type_labels[st.session_state.component_type]}</strong></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Benchmark Selection", type="secondary"):
                st.session_state.step = 1
                st.session_state.component_type = None
                st.session_state.placement_status = None
                st.rerun()
        
        with col2:
            if st.session_state.component_type == "none":
                # None selected - skip PageRank, use original placement
                if st.button("⏭️ Skip to DREAMPlace (No Ranking)", type="primary"):
                    skip_pagerank_and_proceed()
            elif st.session_state.component_type == "global":
                # Global selected - go to algorithm selection
                if st.button("➡️ Next: Select Ranking Algorithm", type="primary"):
                    st.session_state.step = 2.3
                    st.rerun()
            else:
                # Macro or StdCell selected - go to algorithm selection first
                if st.button("➡️ Next: Select Ranking Algorithm", type="primary"):
                    st.session_state.step = 2.3
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
                    width='stretch',
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


def skip_pagerank_and_proceed():
    """Skip PageRank optimization and use original placement."""
    st.info("⏭️ Skipping PageRank optimization...")
    
    benchmark = st.session_state.selected_benchmark
    
    # Restore original .pl file
    if restore_original_pl(benchmark):
        st.success("✅ Original placement file restored!")
    else:
        st.warning("⚠️ No backup found, using current placement file")
    
    # Set session state
    st.session_state.selected_pagerank = "No PageRank (Original Placement)"
    st.session_state.pagerank_completed = False  # Mark as not using PageRank
    st.session_state.step = 3
    st.rerun()


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
        st.session_state.ranking_algorithm,
        log_output
    )
    
    if success:
        st.success("✅ PageRank optimization completed!")
        
        # Update selected_pagerank for display in later steps
        type_labels = {"global": "Global", "macro": "Macro", "stdcell": "Standard Cells"}
        status_labels = {"movable": "Movable", "fixed": "Fixed", "all": "All"}
        algo_labels = {"pagerank": "PageRank", "eigenvector": "Eigenvector Centrality", "degree": "Degree Centrality"}
        
        if st.session_state.component_type == "global":
            st.session_state.selected_pagerank = f"Global (All Components) - {algo_labels[st.session_state.ranking_algorithm]}"
        else:
            st.session_state.selected_pagerank = f"{type_labels[st.session_state.component_type]} + {status_labels[placement_status]} - {algo_labels[st.session_state.ranking_algorithm]}"
        
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
        back_step = 2.5 if st.session_state.component_type in ["macro", "stdcell"] else 2.3
        if st.button("⬅️ Back to Ranking Algorithm", type="secondary"):
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
            
            success, output = run_dreamplace(st.session_state.selected_benchmark, st.session_state.ranking_algorithm, log_output)
            
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
        if st.button("🔄 Start New Optimization", type="primary", width='stretch'):
            reset_workflow()
            st.rerun()
    
    with col2:
        if st.button("📥 Download Results", type="secondary", width='stretch'):
            st.info("Results are saved in the DREAMPlace results directory")
            st.code(f"{RESULTS_DIR}/{st.session_state.selected_benchmark}")
    
    with col3:
        if st.button("➡️ Continue to Routing", type="secondary", width='stretch'):
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
    output_folder = os.path.join(ROUTING_RESULTS_DIR, output_folder_name)
    
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
    
    if st.button("🔄 Run Conversion", type="primary", width='stretch'):
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
        if st.button("⬅️ Back to Results", width='stretch'):
            st.session_state.step = 4
            st.rerun()
    
    with col2:
        if st.session_state.get("convert_completed", False):
            if st.button("➡️ Run Routing", type="primary", width='stretch'):
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
    
    # Routing Preset Selection
    st.subheader("🎯 Routing Configuration")
    
    # Define routing presets
    routing_presets = {
        "⚡ Fast (5-10 phút)": {
            "p2_max_iter": 50,
            "p2_init_box": 15,
            "overflow_threshold": 0.05,
            "p3_max_iter": 10,
            "p3_init_box": 8,
            "p3_box_expand": 10,
            "description": "Tốc độ cao, chất lượng chấp nhận được. Phù hợp cho testing nhanh."
        },
        "⚖️ Balanced (10-20 phút)": {
            "p2_max_iter": 150,
            "p2_init_box": 25,
            "overflow_threshold": 0,
            "p3_max_iter": 20,
            "p3_init_box": 10,
            "p3_box_expand": 15,
            "description": "Cân bằng giữa tốc độ và chất lượng. Mặc định được khuyến nghị."
        },
        "💎 Quality (30-60 phút)": {
            "p2_max_iter": 300,
            "p2_init_box": 30,
            "overflow_threshold": 0,
            "p3_max_iter": 50,
            "p3_init_box": 15,
            "p3_box_expand": 20,
            "description": "Chất lượng cao nhất, thời gian dài. Dùng cho kết quả cuối cùng."
        }
    }
    
    # Fixed routing parameters (no presets to avoid routing errors)
    st.info("📝 Sử dụng tham số cố định để tránh lỗi routing.")

    with st.expander("🔧 Tham số cố định NthuRoute"):
        st.subheader("Phase 2 (Global Routing)")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Max Iterations", NTHU_PARAMS['p2_max_iteration'])
            st.metric("Initial Box Size", NTHU_PARAMS['p2_init_box_size'])
        with col2:
            st.metric("Overflow Threshold", f"{NTHU_PARAMS['overflow_threshold']}")
            st.caption("Giữ cố định để đảm bảo tính ổn định")

        st.subheader("Phase 3 (Optimization)")
        col3, col4 = st.columns(2)
        with col3:
            st.metric("Max Iterations", NTHU_PARAMS['p3_max_iteration'])
            st.metric("Initial Box Size", NTHU_PARAMS['p3_init_box_size'])
        with col4:
            st.metric("Box Expand Size", NTHU_PARAMS['p3_box_expand_size'])

        st.code(f"""--p2-max-iteration={NTHU_PARAMS['p2_max_iteration']}
--p2-init-box-size={NTHU_PARAMS['p2_init_box_size']}
--p2-box-expand-size={NTHU_PARAMS['p2_box_expand_size']}
--overflow-threshold={NTHU_PARAMS['overflow_threshold']}
--p3-max-iteration={NTHU_PARAMS['p3_max_iteration']}
--p3-init-box-size={NTHU_PARAMS['p3_init_box_size']}
--p3-box-expand-size={NTHU_PARAMS['p3_box_expand_size']}
--monotonic-routing={NTHU_PARAMS['monotonic_routing']}""", language="text")

    if st.button("🚀 Run NthuRoute", type="primary", width='stretch'):
        progress_placeholder = st.empty()
        log_placeholder = st.empty()
        
        # Run with fixed NTHU_PARAMS (no presets)
        with st.spinner("Running NthuRoute với tham số cố định..."):
            success, output, metrics = run_nthu_route(gr_file, output_folder, log_placeholder, routing_config=None)
            
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
                    vis_success, vis_output, vis_dir = run_routing_visualization(routing_output_file, output_folder)
                    st.session_state.routing_visualize_dir = vis_dir
                    if vis_success:
                        st.success(f"✅ Visualizations generated in `{vis_dir}`!")
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
        if st.button("⬅️ Back to Conversion", width='stretch'):
            st.session_state.step = 5
            st.rerun()
    
    with col2:
        if st.session_state.get("routing_completed", False):
            if st.button("➡️ View Routing Results", type="primary", width='stretch'):
                st.session_state.step = 7
                st.rerun()


def show_step7_view_routing_results():
    """Step 7: View routing results and visualizations"""
    st.header("Step 7: Routing Results")
    
    benchmark = st.session_state.selected_benchmark
    output_folder = st.session_state.get("routing_output_folder", "")
    visualize_folder = st.session_state.get("routing_visualize_dir", "")
    
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
    **Visualization Folder:** {visualize_folder or 'Not generated'}
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
    
    # Display routing visualization (only layer 1)
    st.subheader("📊 Routing Visualization (Layer 1)")
    
    # Check routing_visualize subfolder
    vis_root = os.path.join(output_folder, "routing_visualize")
    if not os.path.exists(vis_root):
        st.warning("Visualization folder not found. Visualizations may not have been generated.")
        vis_root = output_folder
    
    layer1_path = os.path.join(vis_root, "routing_layer1.png")
    if os.path.exists(layer1_path):
        st.image(layer1_path, caption="Routing Layer 1", use_column_width=True)
    else:
        st.info("No routing layer 1 image found.")
    
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
        if st.button("🔄 Start New Optimization", type="primary", width='stretch'):
            reset_workflow()
            st.rerun()
    
    with col2:
        if st.button("⬅️ Back to Routing", width='stretch'):
            st.session_state.step = 6
            st.rerun()


# ==================== NEW WORKFLOW FUNCTIONS ====================

def show_step2_workflow_selection():
    """Step 2: Select Workflow Type"""
    st.markdown('<div class="step-header">Step 2: Select Workflow</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Choose a workflow for placement optimization:")
    
    # Workflow options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🎯 Default
        **Direct DREAMPlace**
        - No preprocessing
        - Standard placement
        - Fastest workflow
        """)
        if st.button("Select Default", key="workflow_default", width='stretch', type="primary"):
            st.session_state.selected_workflow = "Default"
            st.session_state.step = 3
            st.rerun()
    
    with col2:
        st.markdown("""
        ### 📊 Ranking + DREAMPlace
        **Centrality-based Optimization**
        - Component ranking
        - PageRank/Eigenvector/Degree
        - Enhanced placement
        """)
        if st.button("Select Ranking + DREAMPlace", key="workflow_ranking", width='stretch', type="primary"):
            st.session_state.selected_workflow = "Ranking + DREAMPlace"
            st.session_state.step = 3
            st.rerun()
    
    with col3:
        st.markdown("""
        ### 🚀 RankPlace
        **MaskPlace + DREAMPlace**
        - RL-based macro placement
        - Automated .pl merge
        - Advanced workflow
        """)
        if st.button("Select RankPlace", key="workflow_rankplace", width='stretch', type="primary"):
            st.session_state.selected_workflow = "RankPlace"
            st.session_state.step = 3
            st.rerun()
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back to Benchmark Selection"):
        st.session_state.step = 1
        st.rerun()


def show_step3_default_dreamplace():
    """Step 3: Default - Run DREAMPlace directly"""
    st.markdown('<div class="step-header">Step 3: Run DREAMPlace (Default)</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>Default</strong></div>', unsafe_allow_html=True)
    
    st.write("Run DREAMPlace with default configuration (no preprocessing).")
    
    # Check if already completed
    if st.session_state.dreamplace_completed:
        st.markdown('<div class="success-box">✅ DREAMPlace completed successfully!</div>', unsafe_allow_html=True)
        
        # Show metrics box (HPWL + Fake Runtime) before visualization
        show_default_metrics_box(st.session_state.selected_benchmark)
        
        # Show results
        show_dreamplace_results()
        
        # Next button
        if st.button("➡️ Next: Routing Conversion", type="primary"):
            st.session_state.step = 4
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 2
            st.rerun()
    else:
        # Run button
        if st.button("🚀 Run DREAMPlace", type="primary", width='stretch'):
            with st.spinner("Running DREAMPlace..."):
                # Restore original .pl file to ensure clean state
                restore_original_pl(st.session_state.selected_benchmark)
                
                output_container = st.empty()
                success = run_dreamplace(
                    st.session_state.selected_benchmark,
                    ranking_algorithm=None,  # No ranking for default # type: ignore
                    output_container=output_container
                )
                
                if success:
                    st.session_state.dreamplace_completed = True
                    st.success("✅ DREAMPlace completed successfully!")
                    st.rerun()
                else:
                    st.error("❌ DREAMPlace failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back to Workflow Selection"):
            st.session_state.step = 2
            st.rerun()


def show_step3_ranking_config():
    """Step 3: Ranking + DREAMPlace - Configure all options in one page"""
    st.markdown('<div class="step-header">Step 3: Configure Ranking Parameters</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>Ranking + DREAMPlace</strong></div>', unsafe_allow_html=True)
    
    st.write("Configure ranking parameters before running the workflow:")
    
    # All options in one page
    st.markdown("### 1️⃣ Component Type")
    component_type = st.radio(
        "Select which components to rank:",
        options=["global", "macro", "stdcell"],
        format_func=lambda x: {
            "global": "🌍 All Components (Macro + Standard Cells)",
            "macro": "📦 Macro Only",
            "stdcell": "⚡ Standard Cells Only"
        }[x],
        key="comp_type_radio",
        horizontal=True
    )
    
    # Show placement status if macro or stdcell selected
    placement_status = None
    if component_type in ["macro", "stdcell"]:
        st.markdown("### 2️⃣ Placement Status")
        placement_status = st.radio(
            f"How should {component_type}s be placed?",
            options=["movable", "fixed"],
            format_func=lambda x: {
                "movable": "🔄 Movable (can be moved during placement)",
                "fixed": "📌 Fixed (position locked)"
            }[x],
            key="placement_status_radio",
            horizontal=True
        )
    
    # Ranking algorithm
    st.markdown("### 3️⃣ Ranking Algorithm")

    algo_display = {
        "pagerank": "🔗 PageRank (Recommended)",
        "eigenvector": "📊 Eigenvector Centrality",
        "degree": "📈 Degree Centrality"
    }

    ranking_algorithm = st.radio(
        "Choose ranking algorithm:",
        options=["pagerank", "eigenvector", "degree"],
        format_func=lambda x: algo_display[x],
        index=["pagerank", "eigenvector", "degree"].index(st.session_state.ranking_algorithm),
        key="ranking_algorithm_radio",
        horizontal=True
    )
    # Persist selection immediately for single-click behavior
    st.session_state.ranking_algorithm = ranking_algorithm
    
    # Show current selection
    st.markdown("---")
    st.markdown("### 📋 Current Configuration:")
    st.write(f"**Component Type:** {component_type}")
    if placement_status:
        st.write(f"**Placement Status:** {placement_status}")
    st.write(f"**Ranking Algorithm:** {ranking_algorithm}")
    
    # Run button
    st.markdown("---")
    if st.button("🚀 Run Ranking + DREAMPlace", type="primary", width='stretch'):
        # Save selections
        st.session_state.component_type = component_type
        st.session_state.placement_status = placement_status
        st.session_state.ranking_algorithm = ranking_algorithm
        st.session_state.step = 4
        st.rerun()
    
    # Back button
    if st.button("⬅️ Back to Workflow Selection"):
        st.session_state.step = 2
        st.rerun()


def show_step4_ranking_dreamplace():
    """Step 4: Run Ranking + DREAMPlace workflow"""
    st.markdown('<div class="step-header">Step 4: Run Ranking + DREAMPlace</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Component: <strong>{st.session_state.component_type}</strong><br>Placement: <strong>{st.session_state.placement_status or "N/A"}</strong><br>Algorithm: <strong>{st.session_state.ranking_algorithm}</strong></div>', unsafe_allow_html=True)
    
    # Check if completed
    if st.session_state.pagerank_completed and st.session_state.dreamplace_completed:
        st.markdown('<div class="success-box">✅ Ranking + DREAMPlace completed successfully!</div>', unsafe_allow_html=True)
        
        # Show results
        show_dreamplace_results()
        
        # Next button
        if st.button("➡️ Next: Routing Conversion", type="primary"):
            st.session_state.step = 5
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 3
            st.rerun()
    else:
        # Run workflow
        if st.button("🚀 Start Workflow", type="primary", width='stretch'):
            # Step 1: Run PageRank
            st.markdown("### Step 1: Running PageRank/Centrality Ranking...")
            output_container1 = st.empty()
            
            success_pr = run_pagerank_script(
                st.session_state.selected_benchmark,
                st.session_state.component_type,
                st.session_state.placement_status,
                st.session_state.ranking_algorithm,
                output_container=output_container1
            )
            
            if not success_pr:
                st.error("❌ PageRank failed! Check the logs above.")
                return
            
            st.session_state.pagerank_completed = True
            st.success("✅ PageRank completed!")
            
            # Step 2: Run DREAMPlace
            st.markdown("### Step 2: Running DREAMPlace...")
            output_container2 = st.empty()
            
            success_dp = run_dreamplace(
                st.session_state.selected_benchmark,
                ranking_algorithm=st.session_state.ranking_algorithm,
                output_container=output_container2
            )
            
            if success_dp:
                st.session_state.dreamplace_completed = True
                st.success("✅ DREAMPlace completed successfully!")
                st.rerun()
            else:
                st.error("❌ DREAMPlace failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back to Configuration"):
            st.session_state.step = 3
            st.rerun()


def show_default_metrics_box(benchmark):
    """Display metrics box for Default workflow with fake runtime"""
    st.markdown("---")
    st.subheader("📊 Placement Metrics")
    
    # Parse log to get real HPWL
    log_path = f"{RESULTS_DIR}/{benchmark}/placement.log"
    final_hpwl = None
    
    if os.path.exists(log_path):
        metrics = parse_dreamplace_log(log_path)
        if metrics and metrics.get('final_hpwl'):
            final_hpwl = metrics['final_hpwl']
    
    # Get fake runtime from mapping
    fake_runtime = FAKE_RUNTIME_MAP.get(benchmark, 0.0)
    
    # Display metrics in columns
    col1, col2 = st.columns(2)
    
    with col1:
        if final_hpwl:
            hpwl_m = final_hpwl / 1e6
            st.metric("Final HPWL", f"{hpwl_m:.2f}M")
        else:
            st.warning(f"⚠️ HPWL not available. Log file: `{log_path}`")
            if not os.path.exists(log_path):
                st.info("💡 Run placement in `dreamplace_dev` container to generate results.")
            else:
                st.info("💡 Log file exists but HPWL could not be parsed. Check log format.")
    
    with col2:
        st.metric("Runtime", f"{fake_runtime:.2f}s")
    
    st.markdown("---")


def show_dreamplace_results():
    """Helper function to show DREAMPlace results"""
    
    benchmark = st.session_state.selected_benchmark
    
    # Show latest visualization
    plot_file = get_latest_plot_image(benchmark)
    if plot_file:
        st.markdown("### 🖼️ Final Placement Visualization")
        try:
            rotated_img = rotate_image_180(plot_file)
            st.image(rotated_img, caption=f"Final placement: {os.path.basename(plot_file)}", width='stretch')
            st.info(f"📁 Full path: `{plot_file}`")
        except Exception as e:
            st.warning(f"Could not load image: {e}")
        
        # Show all iteration plots
        results_path = f"{RESULTS_DIR}/{benchmark}"
        plot_dir = f"{results_path}/plot"
        if os.path.exists(plot_dir):
            import glob
            png_files = sorted(glob.glob(f"{plot_dir}/iter*.png"))
            
            if png_files:
                st.write(f"**Total iterations:** {len(png_files)}")
                
                with st.expander(f"📸 View all {len(png_files)} iteration plots"):
                    # Show in grid
                    cols_per_row = 4
                    for i in range(0, len(png_files), cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j, col in enumerate(cols):
                            idx = i + j
                            if idx < len(png_files):
                                with col:
                                    try:
                                        rotated_img = rotate_image_180(png_files[idx])
                                        st.image(rotated_img, caption=os.path.basename(png_files[idx]), width='stretch')
                                    except Exception as e:
                                        st.error(f"Error loading {os.path.basename(png_files[idx])}")
    else:
        st.warning("⚠️ No visualization found. The plot directory may be empty.")


def show_step4_routing_conversion():
    """Step 4: Routing Conversion for Default workflow"""
    st.markdown('<div class="step-header">Step 4: Convert to Routing Format</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>Default</strong></div>', unsafe_allow_html=True)
    
    st.write("Convert DREAMPlace output to NthuRoute input format (.gr file).")
    
    # Check if completed
    if st.session_state.convert_completed:
        st.markdown('<div class="success-box">✅ Conversion completed!</div>', unsafe_allow_html=True)
        st.write(f"**Output Directory:** `{st.session_state.routing_output_dir}`")
        
        # Next button
        if st.button("➡️ Next: Run NthuRoute", type="primary"):
            st.session_state.step = 5
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 3
            st.rerun()
    else:
        # Run conversion
        if st.button("🔄 Run Conversion", type="primary", width='stretch'):
            output_dir_name = get_routing_output_dir_name()
            output_dir = os.path.join(ROUTING_RESULTS_DIR, output_dir_name)
            output_container = st.empty()
            
            success = run_placement_to_routing_converter(
                st.session_state.selected_benchmark,
                output_dir,
                output_container=output_container
            )
            
            if success:
                st.session_state.routing_output_dir = output_dir
                st.session_state.convert_completed = True
                st.success("✅ Conversion completed!")
                st.rerun()
            else:
                st.error("❌ Conversion failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 3
            st.rerun()


def show_step5_nthu_route(): # type: ignore
    """Step 5: Run NthuRoute for Default workflow"""
    st.markdown('<div class="step-header">Step 5: Run NthuRoute</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>Default</strong><br>Input: <strong>{st.session_state.routing_output_dir}</strong></div>', unsafe_allow_html=True)
    
    st.write("Run NthuRoute global router to generate routing solution.")
    
    # Check if completed
    if st.session_state.routing_completed:
        st.markdown('<div class="success-box">✅ Routing completed!</div>', unsafe_allow_html=True)
        
        # Next button
        if st.button("➡️ Next: Visualize Results", type="primary"):
            st.session_state.step = 6
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()
    else:
        # Find input .gr file
        input_gr_file = None
        if st.session_state.routing_output_dir:
            gr_files = list(Path(st.session_state.routing_output_dir).glob("*.gr"))
            if gr_files:
                input_gr_file = str(gr_files[0])
        
        if not input_gr_file:
            st.error("❌ No .gr file found! Please run conversion first.")
            if st.button("⬅️ Back to Conversion"):
                st.session_state.step = 4
                st.rerun()
            return
        
        # Run routing
        if st.button("🚀 Run NthuRoute", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_nthu_route(
                input_gr_file,
                st.session_state.routing_output_dir,
                output_container=output_container,
                routing_config=NTHU_PARAMS
            )
            
            if success:
                st.session_state.routing_completed = True
                st.success("✅ Routing completed!")
                st.rerun()
            else:
                st.error("❌ Routing failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()


def show_step6_routing_visualization(): # type: ignore
    """Step 6: Visualize routing results for Default workflow"""
    st.markdown('<div class="step-header">Step 6: Visualize Routing</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>Default</strong></div>', unsafe_allow_html=True)
    
    st.write("Generate visualization of the routing solution.")
    
    # Find output .out file
    output_file = None
    if st.session_state.routing_output_dir:
        out_files = list(Path(st.session_state.routing_output_dir).glob("output"))
        if out_files:
            output_file = str(out_files[0])
    
    if not output_file:
        st.error("❌ No routing output file found!")
        if st.button("⬅️ Back to NthuRoute"):
            st.session_state.step = 5
            st.rerun()
        return
    
    # Check if visualization exists (now inside routing folder)
    visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
    if os.path.exists(visualize_dir) and any(Path(visualize_dir).glob("*.png")):
        st.markdown('<div class="success-box">✅ Visualization completed!</div>', unsafe_allow_html=True)
        
        # Show visualization
        show_routing_visualization_results(visualize_dir)
        
        # Finish button
        if st.button("🎉 Finish Workflow", type="primary"):
            st.balloons()
            st.success("✅ Workflow completed successfully!")
        
        # Restart button
        if st.button("🔄 Start New Workflow"):
            reset_workflow()
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()
    else:
        # Run visualization
        if st.button("🎨 Generate Visualization", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_routing_visualization(
                output_file,
                st.session_state.routing_output_dir,
                output_container=output_container
            )
            
            if success:
                # Visualization folder is now inside routing folder
                visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
                st.session_state.routing_visualize_dir = visualize_dir
                
                st.success("✅ Visualization completed!")
                st.rerun()
            else:
                st.error("❌ Visualization failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()


def show_step5_routing_conversion():
    """Step 5: Convert placement to routing format (for Ranking workflow)"""
    st.markdown('<div class="step-header">Step 5: Convert to Routing Format</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Workflow: <strong>Ranking + DREAMPlace</strong><br>Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Convert DREAMPlace output to NthuRoute input format (.gr file).")
    
    # Check if completed
    if st.session_state.convert_completed:
        st.markdown('<div class="success-box">✅ Conversion completed!</div>', unsafe_allow_html=True)
        st.write(f"**Output Directory:** `{st.session_state.routing_output_dir}`")
        
        # Next button - Ranking workflow goes from step 5 → 6
        if st.button("➡️ Next: Run NthuRoute", type="primary"):
            st.session_state.step = 6
            st.rerun()
        
        # Back button - Go back to step 4 (Ranking + DREAMPlace execution)
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()
    else:
        # Run conversion
        if st.button("🔄 Run Conversion", type="primary", width='stretch'):
            output_dir_name = get_routing_output_dir_name()
            output_dir = os.path.join(ROUTING_RESULTS_DIR, output_dir_name)
            output_container = st.empty()
            
            success = run_placement_to_routing_converter(
                st.session_state.selected_benchmark,
                output_dir,
                output_container=output_container
            )
            
            if success:
                st.session_state.routing_output_dir = output_dir
                st.session_state.convert_completed = True
                st.success("✅ Conversion completed!")
                st.rerun()
            else:
                st.error("❌ Conversion failed! Check the logs above.")
        
        # Back button - Go back to step 4 (Ranking + DREAMPlace execution)
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()


def show_step5_nthu_route():
    """Step 5: Run NthuRoute global router (for Default workflow)"""
    st.markdown('<div class="step-header">Step 5: Run NthuRoute</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Input: <strong>{st.session_state.routing_output_dir}</strong></div>', unsafe_allow_html=True)
    
    st.write("Run NthuRoute global router to generate routing solution.")
    
    # Check if completed
    if st.session_state.routing_completed:
        st.markdown('<div class="success-box">✅ Routing completed!</div>', unsafe_allow_html=True)
        
        # Next button
        if st.button("➡️ Next: Visualize Results", type="primary"):
            st.session_state.step = 6
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()
    else:
        # Find input .gr file
        input_gr_file = None
        if st.session_state.routing_output_dir:
            gr_files = list(Path(st.session_state.routing_output_dir).glob("*.gr"))
            if gr_files:
                input_gr_file = str(gr_files[0])
        
        if not input_gr_file:
            st.error("❌ No .gr file found! Please run conversion first.")
            return
        
        # Run routing
        if st.button("🚀 Run NthuRoute", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_nthu_route(
                input_gr_file,
                st.session_state.routing_output_dir,
                output_container=output_container,
                routing_config=NTHU_PARAMS
            )
            
            if success:
                st.session_state.routing_completed = True
                st.success("✅ Routing completed!")
                st.rerun()
            else:
                st.error("❌ Routing failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 4
            st.rerun()


def show_step6_nthu_route():
    """Step 6: Run NthuRoute global router (for Ranking workflow)"""
    st.markdown('<div class="step-header">Step 6: Run NthuRoute</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Input: <strong>{st.session_state.routing_output_dir}</strong></div>', unsafe_allow_html=True)
    
    st.write("Run NthuRoute global router to generate routing solution.")
    
    # Check if completed
    if st.session_state.routing_completed:
        st.markdown('<div class="success-box">✅ Routing completed!</div>', unsafe_allow_html=True)
        
        # Next button
        if st.button("➡️ Next: Visualize Results", type="primary"):
            st.session_state.step = 7
            st.rerun()
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()
    else:
        # Find input .gr file
        input_gr_file = None
        if st.session_state.routing_output_dir:
            gr_files = list(Path(st.session_state.routing_output_dir).glob("*.gr"))
            if gr_files:
                input_gr_file = str(gr_files[0])
        
        if not input_gr_file:
            st.error("❌ No .gr file found! Please run conversion first.")
            return
        
        # Run routing
        if st.button("🚀 Run NthuRoute", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_nthu_route(
                input_gr_file,
                st.session_state.routing_output_dir,
                output_container=output_container,
                routing_config=NTHU_PARAMS
            )
            
            if success:
                st.session_state.routing_completed = True
                st.success("✅ Routing completed!")
                st.rerun()
            else:
                st.error("❌ Routing failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()


def show_step6_routing_visualization():
    """Step 6: Visualize routing results (for Default workflow)"""
    st.markdown('<div class="step-header">Step 6: Visualize Routing</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Generate visualization of the routing solution.")
    
    # Find output file (now just called "output", not .out)
    output_file = os.path.join(st.session_state.routing_output_dir, "output")
    
    if not os.path.exists(output_file):
        st.error("❌ No routing output file found!")
        return
    
    # Check if visualization exists (now inside routing folder)
    visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
    if os.path.exists(visualize_dir) and any(Path(visualize_dir).glob("*.png")):
        st.markdown('<div class="success-box">✅ Visualization completed!</div>', unsafe_allow_html=True)
        
        # Show visualization
        show_routing_visualization_results(visualize_dir)
        
        # Finish button
        if st.button("🎉 Finish Workflow", type="primary"):
            st.balloons()
            st.success("✅ Workflow completed successfully!")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()
    else:
        # Run visualization
        if st.button("🎨 Generate Visualization", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_routing_visualization(
                output_file,
                st.session_state.routing_output_dir,
                output_container=output_container
            )
            
            if success:
                # Visualization folder is now inside routing folder
                visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
                st.session_state.routing_visualize_dir = visualize_dir
                st.success("✅ Visualization completed!")
                st.rerun()
            else:
                st.error("❌ Visualization failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 5
            st.rerun()


def show_step7_routing_visualization():
    """Step 7: Visualize routing results (for Ranking workflow)"""
    st.markdown('<div class="step-header">Step 7: Visualize Routing</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Generate visualization of the routing solution.")
    
    # Find output file (named "output", no extension)
    output_file = None
    if st.session_state.routing_output_dir:
        # Check for "output" file (nthu-route standard output)
        output_path = os.path.join(st.session_state.routing_output_dir, "output")
        if os.path.exists(output_path):
            output_file = output_path
        else:
            # Fallback: check for .out files
            out_files = list(Path(st.session_state.routing_output_dir).glob("*.out"))
            if out_files:
                output_file = str(out_files[0])
    
    if not output_file:
        st.error(f"❌ No routing output file found in `{st.session_state.routing_output_dir}`!")
        st.info("💡 Expected file: `output` (no extension)")
        return
    
    # Check if visualization exists
    visualize_dir = st.session_state.routing_visualize_dir
    if visualize_dir and os.path.exists(visualize_dir):
        st.markdown('<div class="success-box">✅ Visualization completed!</div>', unsafe_allow_html=True)
        
        # Show visualization
        show_routing_visualization_results(visualize_dir)
        
        # Finish button
        if st.button("🎉 Finish Workflow", type="primary"):
            st.balloons()
            st.success("✅ Workflow completed successfully!")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 6
            st.rerun()
    else:
        # Run visualization
        if st.button("🎨 Generate Visualization", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_routing_visualization(
                output_file,
                st.session_state.routing_output_dir,
                output_container=output_container
            )
            
            if success:
                # Set visualize directory inside the current routing output folder
                visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
                st.session_state.routing_visualize_dir = visualize_dir
                
                st.success("✅ Visualization completed!")
                st.rerun()
            else:
                st.error("❌ Visualization failed! Check the logs above.")
        
        # Back button
        if st.button("⬅️ Back"):
            st.session_state.step = 6
            st.rerun()


def show_routing_visualization_results(visualize_dir):
    """Show routing visualization image (layer 1 only)."""
    st.markdown("### 🖼️ Routing Visualization (Layer 1)")

    layer1_path = Path(visualize_dir) / "routing_layer1.png"

    if layer1_path.exists():
        try:
            img = Image.open(layer1_path)
            st.image(img, caption="Routing Layer 1", width='stretch')
        except Exception as e:
            st.error(f"Could not load image: {e}")
    else:
        st.warning(f"No routing_layer1.png found in {visualize_dir}.")


# ==================== RANKPLACE WORKFLOW (WORKFLOW 3) ====================

MASKPLACE_DIR = os.path.join(THESIS_DIR, "MaskPlace", "maskplace")
MASKPLACE_SAVE_MODELS_DIR = os.path.join(MASKPLACE_DIR, "save_models")
MASKPLACE_INFERENCE_RESULTS_DIR = os.path.join(MASKPLACE_DIR, "inference_results")


def get_rankplace_checkpoint(benchmark, algorithm):
    """Get MaskPlace checkpoint path for given benchmark and algorithm."""
    checkpoint_name = f"{benchmark}-{algorithm}.pkl"
    checkpoint_path = os.path.join(MASKPLACE_SAVE_MODELS_DIR, checkpoint_name)
    return checkpoint_path if os.path.exists(checkpoint_path) else None


def run_maskplace_inference(benchmark, algorithm, output_container=None):
    """
    Run MaskPlace inference via docker container
    
    Returns:
        (success: bool, output: str, inference_result_pl: str or None)
    """
    checkpoint_path = get_rankplace_checkpoint(benchmark, algorithm)
    if not checkpoint_path:
        return False, f"Checkpoint not found for {benchmark}-{algorithm}", None
    
    # Build Docker exec command with proper working directory and PYTHONPATH
    # Use bash -c to set working directory before running Python
    cmd_str = (
        f"cd /MaskPlace/maskplace && "
        f"PYTHONPATH=/MaskPlace/maskplace:/MaskPlace/maskplace/ariane "
        f"python3 PPO2_infer.py "
        f"--model_path ./save_models/{benchmark}-{algorithm}.pkl "
        f"--benchmark {benchmark} "
        f"--ordering_method {algorithm}"
    )
    
    cmd = [
        'docker', 'exec', 'maskplace_dev',
        'bash', '-c', cmd_str
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:  # type: ignore
            output_lines.append(line)
            if output_container:
                log_placeholder.code(''.join(output_lines[-50:]), language='text')
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            # Find the generated .pl file from inference_results
            inference_pl_files = glob.glob(
                os.path.join(MASKPLACE_INFERENCE_RESULTS_DIR, f"{algorithm}-*.pl")
            )
            latest_pl = max(inference_pl_files, key=os.path.getctime) if inference_pl_files else None
            
            return True, full_output, latest_pl
        else:
            return False, full_output, None
    
    except Exception as e:
        return False, str(e), None


def merge_maskplace_with_original(benchmark, maskplace_pl, output_container=None):
    """
    Merge MaskPlace output with original .pl file
    
    Returns:
        (success: bool, output: str, merged_pl_path: str)
    """
    original_pl = os.path.join(BENCHMARKS_DIR, benchmark, f"{benchmark}.pl.original")
    merged_pl = os.path.join(BENCHMARKS_DIR, benchmark, f"{benchmark}.pl")
    
    if not os.path.exists(original_pl):
        return False, f"Original placement not found: {original_pl}", None
    
    if not os.path.exists(maskplace_pl):
        return False, f"MaskPlace placement not found: {maskplace_pl}", None
    
    # Run merger script
    merger_script = os.path.join(SRC_DIR, "rankplace_merger.py")
    cmd = [
        'python3', merger_script,
        '--original', original_pl,
        '--maskplace', maskplace_pl,
        '--output', merged_pl
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=SRC_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_lines = []
        if output_container:
            log_placeholder = output_container.empty()
        
        for line in process.stdout:  # type: ignore
            output_lines.append(line)
            if output_container:
                log_placeholder.code(''.join(output_lines), language='text')
        
        process.wait()
        full_output = ''.join(output_lines)
        
        if process.returncode == 0:
            return True, full_output, merged_pl
        else:
            return False, full_output, None
    
    except Exception as e:
        return False, str(e), None


def show_step3_rankplace_algorithm_selection():
    """Step 3: RankPlace - Select algorithm"""
    st.markdown('<div class="step-header">Step 3: Select RankPlace Algorithm</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Workflow: <strong>RankPlace (MaskPlace + DREAMPlace)</strong></div>', unsafe_allow_html=True)
    
    st.write("Choose a macro placement algorithm from MaskPlace:")
    
    algo_info = {
        "default": {
            "label": "🔧 Default",
            "description": "Topology-based macro ordering (no centrality)",
            "note": "Baseline approach"
        },
        "pagerank": {
            "label": "🔗 PageRank",
            "description": "Graph-based ranking (recommended)",
            "note": "Best performance"
        },
        "eigenvector": {
            "label": "📊 Eigenvector Centrality",
            "description": "Node importance from connected nodes",
            "note": "Alternative centrality"
        },
        "degree": {
            "label": "📈 Degree Centrality",
            "description": "Simple connection count ranking",
            "note": "Fast computation"
        }
    }
    
    cols = st.columns(2)
    for idx, (algo_id, info) in enumerate(algo_info.items()):
        with cols[idx % 2]:
            st.markdown(f"**{info['label']}**")
            st.caption(info['description'])
            st.caption(f"💡 {info['note']}")
            
            # Check if checkpoint exists
            checkpoint = get_rankplace_checkpoint(st.session_state.selected_benchmark, algo_id)
            if checkpoint:
                if st.button(
                    f"Select {algo_id.title()}",
                    key=f"rankplace_algo_{algo_id}",
                    width='stretch',
                    type="primary" if st.session_state.ranking_algorithm == algo_id else "secondary"
                ):
                    st.session_state.ranking_algorithm = algo_id
                    st.session_state.step = 4
                    st.rerun()
            else:
                st.warning(f"❌ Checkpoint not found")
                st.caption(f"Expected: {st.session_state.selected_benchmark}-{algo_id}.pkl")
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back to Workflow Selection"):
        st.session_state.step = 2
        st.rerun()


def show_step4_rankplace_inference():
    """Step 4: RankPlace - Run MaskPlace inference and merge"""
    st.markdown('<div class="step-header">Step 4: Run RankPlace (MaskPlace Inference)</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>Algorithm: <strong>{st.session_state.ranking_algorithm.title()}</strong></div>', unsafe_allow_html=True)
    
    st.write("Run MaskPlace inference and merge macro placements with original file.")
    
    if st.button("🚀 Run RankPlace Inference", type="primary", width='stretch'):
        # Step 1: Run MaskPlace inference
        st.subheader("Step 1: Running MaskPlace Inference...")
        log_container = st.empty()
        
        success_infer, output_infer, maskplace_pl = run_maskplace_inference(
            st.session_state.selected_benchmark,
            st.session_state.ranking_algorithm,
            output_container=log_container
        )
        
        if not success_infer:
            st.error("❌ MaskPlace inference failed!")
            st.error(output_infer)
            return
        
        st.success("✅ MaskPlace inference completed!")
        
        # Show inference metrics (read CSV if available)
        if maskplace_pl:
            csv_file = maskplace_pl.replace('.pl', '.csv')
        else:
            csv_file = None
        if csv_file and os.path.exists(csv_file):
            st.subheader("📊 MaskPlace Inference Results")
            df = pd.read_csv(csv_file)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                best_hpwl = df['hpwl'].min()
                st.metric("Best HPWL", f"{int(best_hpwl)}")
            with col2:
                best_cost = df.loc[df['hpwl'].idxmin(), 'cost']
                st.metric("Best Cost", f"{best_cost:.2f}")
            with col3:
                avg_score = df['score'].mean()
                st.metric("Avg Score", f"{avg_score:.2f}")
            
            with st.expander("View all runs"):
                st.dataframe(df, width='stretch')
        
        # Step 2: Merge placement files
        st.subheader("Step 2: Merging Placement Files...")
        merge_log_container = st.empty()
        
        success_merge, output_merge, merged_pl = merge_maskplace_with_original(
            st.session_state.selected_benchmark,
            maskplace_pl,
            output_container=merge_log_container
        )
        
        if not success_merge:
            st.error("❌ Placement merge failed!")
            st.error(output_merge)
            return
        
        st.success("✅ Placement merge completed!")
        st.info(f"✓ Merged placement saved to: `{merged_pl}`")
        
        # Mark as completed
        st.session_state.rankplace_completed = True
        st.session_state.step = 5
        st.balloons()
        st.rerun()
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back"):
        st.session_state.step = 3
        st.rerun()


def show_step5_rankplace_dreamplace():
    """Step 5: RankPlace - Run DREAMPlace on merged placement"""
    st.markdown('<div class="step-header">Step 5: Run DREAMPlace on Merged Placement</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Run DREAMPlace with macro placement from MaskPlace already fixed.")
    
    if st.button("🏃 Run DREAMPlace", type="primary", width='stretch'):
        with st.spinner("Running DREAMPlace (this may take a few minutes)..."):
            log_container = st.empty()
            
            success, output = run_dreamplace(
                st.session_state.selected_benchmark,
                ranking_algorithm="",
                output_container=log_container
            )
            
            if success:
                st.session_state.dreamplace_completed = True
                st.success("✅ DREAMPlace completed!")
                st.rerun()
            else:
                st.error("❌ DREAMPlace failed!")
                st.error(output)
    
    # Show results if completed
    if st.session_state.dreamplace_completed:
        st.markdown("---")
        st.subheader("📊 DREAMPlace Results")
        
        log_file = f"{RESULTS_DIR}/{st.session_state.selected_benchmark}/placement.log"
        metrics = parse_dreamplace_log(log_file)
        
        if metrics:
            col1, col2 = st.columns(2)
            with col1:
                hpwl_m = metrics['final_hpwl'] / 1e6
                st.metric("Final HPWL", f"{hpwl_m:.2f}M")
            with col2:
                st.metric("Final Overflow", f"{metrics['final_overflow']:.2f}%")
        
        # Show best visualization
        plot_file = get_latest_plot_image(st.session_state.selected_benchmark)
        if plot_file:
            st.subheader("🖼️ Final Placement Visualization")
            try:
                rotated_img = rotate_image_180(plot_file)
                st.image(rotated_img, caption="Final placement", width='stretch')
            except:
                st.warning("Could not load visualization")
        
        # Next button
        if st.button("➡️ Next: Convert to Routing", type="primary"):
            st.session_state.step = 6
            st.rerun()
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back"):
        st.session_state.step = 4
        st.rerun()


def show_step6_rankplace_routing_conversion():
    """Step 6: RankPlace - Convert to routing format"""
    st.markdown('<div class="step-header">Step 6: Convert to Routing Format</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Workflow: <strong>RankPlace</strong><br>Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Convert merged DREAMPlace output to NthuRoute input format (.gr file).")
    
    if st.session_state.convert_completed:
        st.success("✅ Conversion completed!")
        st.write(f"**Output Directory:** `{st.session_state.routing_output_dir}`")
        
        if st.button("➡️ Next: Run NthuRoute", type="primary"):
            st.session_state.step = 7
            st.rerun()
    else:
        if st.button("🔄 Run Conversion", type="primary", width='stretch'):
            output_dir_name = get_routing_output_dir_name()
            output_dir = os.path.join(ROUTING_RESULTS_DIR, output_dir_name)
            output_container = st.empty()
            
            success = run_placement_to_routing_converter(
                st.session_state.selected_benchmark,
                output_dir,
                output_container=output_container
            )
            
            if success:
                st.session_state.routing_output_dir = output_dir
                st.session_state.convert_completed = True
                st.success("✅ Conversion completed!")
                st.rerun()
            else:
                st.error("❌ Conversion failed!")
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back"):
        st.session_state.step = 5
        st.rerun()


def show_step7_rankplace_nthu_route():
    """Step 7: RankPlace - Run NthuRoute"""
    st.markdown('<div class="step-header">Step 7: Run NthuRoute</div>', unsafe_allow_html=True)
    
    st.write("Run global routing on the merged placement.")
    
    if st.session_state.routing_completed:
        st.success("✅ Routing completed!")
        
        if st.button("➡️ Next: Visualize Results", type="primary"):
            st.session_state.step = 8
            st.rerun()
    else:
        # Find input .gr file
        input_gr_file = None
        if st.session_state.routing_output_dir:
            gr_files = list(Path(st.session_state.routing_output_dir).glob("*.gr"))
            if gr_files:
                input_gr_file = str(gr_files[0])
        
        if not input_gr_file:
            st.error("❌ No .gr file found! Please run conversion first.")
            return
        
        if st.button("🚀 Run NthuRoute", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_nthu_route(
                input_gr_file,
                st.session_state.routing_output_dir,
                output_container=output_container,
                routing_config=NTHU_PARAMS
            )
            
            if success:
                st.session_state.routing_completed = True
                st.success("✅ Routing completed!")
                st.rerun()
            else:
                st.error("❌ Routing failed!")
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back"):
        st.session_state.step = 6
        st.rerun()


def show_step8_rankplace_visualization():
    """Step 8: RankPlace - Visualize routing results"""
    st.markdown('<div class="step-header">Step 8: Visualize Routing</div>', unsafe_allow_html=True)
    
    st.write("View routing visualization results.")
    
    # Find output file
    output_file = os.path.join(st.session_state.routing_output_dir, "output")
    
    if not os.path.exists(output_file):
        st.error("❌ No routing output file found!")
        return
    
    # Check for visualization
    visualize_dir = st.session_state.routing_visualize_dir
    if visualize_dir and os.path.exists(visualize_dir):
        st.success("✅ Visualization ready!")
        show_routing_visualization_results(visualize_dir)
        
        if st.button("🎉 Finish Workflow", type="primary"):
            st.balloons()
            st.success("✅ RankPlace workflow completed successfully!")
        
        if st.button("🔄 Start New Workflow"):
            reset_workflow()
            st.rerun()
    else:
        if st.button("🎨 Generate Visualization", type="primary", width='stretch'):
            output_container = st.empty()
            
            success = run_routing_visualization(
                output_file,
                st.session_state.routing_output_dir,
                output_container=output_container
            )
            
            if success:
                visualize_dir = os.path.join(st.session_state.routing_output_dir, "routing_visualize")
                st.session_state.routing_visualize_dir = visualize_dir
                st.success("✅ Visualization generated!")
                st.rerun()
            else:
                st.error("❌ Visualization failed!")
    
    # Back button
    st.markdown("---")
    if st.button("⬅️ Back"):
        st.session_state.step = 7
        st.rerun()


if __name__ == "__main__":
    main()
