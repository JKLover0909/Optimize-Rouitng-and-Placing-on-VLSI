#!/usr/bin/env python3
"""
DREAMPlace GUI - Streamlit Interface
A complete workflow for IC placement optimization with PageRank
"""

import streamlit as st
import subprocess
import os
import glob
from pathlib import Path
import shutil
from PIL import Image

# Configuration
BASE_DIR = "DREAMPlace/install"
BENCHMARKS_DIR = f"{BASE_DIR}/benchmarks/ispd2005"
RESULTS_DIR = f"{BASE_DIR}/results"
SCRIPTS_DIR = "."

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
if 'pagerank_completed' not in st.session_state:
    st.session_state.pagerank_completed = False
if 'dreamplace_completed' not in st.session_state:
    st.session_state.dreamplace_completed = False

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

def run_pagerank_script(benchmark, script_name, area_threshold=1000, output_container=None):
    """Run PageRank script and return output."""
    script_path = f"{SCRIPTS_DIR}/{script_name}"
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    
    try:
        # Restore original .pl before running PageRank
        restore_original_pl(benchmark)
        
        # Run the script
        if script_name in ['makePL_macro.py', 'makePL_stdcell.py']:
            cmd = ['python3', script_path, benchmark, str(area_threshold)]
        else:
            cmd = ['python3', script_path, benchmark]
        
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
    st.session_state.pagerank_completed = False
    st.session_state.dreamplace_completed = False

# Main App
def main():
    # Header
    st.markdown('<div class="main-header">🔬 DREAMPlace + PageRank Optimizer</div>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    with st.sidebar:
        st.header("📋 Workflow Progress")
        
        # Progress indicators
        if st.session_state.step >= 1:
            st.success("✅ Step 1: Benchmark Selection")
        else:
            st.info("⏳ Step 1: Benchmark Selection")
        
        if st.session_state.step >= 2:
            st.success("✅ Step 2: PageRank Optimization")
        else:
            st.info("⏳ Step 2: PageRank Optimization")
        
        if st.session_state.step >= 3:
            st.success("✅ Step 3: Run DREAMPlace")
        else:
            st.info("⏳ Step 3: Run DREAMPlace")
        
        if st.session_state.dreamplace_completed:
            st.success("✅ Step 4: View Results")
        else:
            st.info("⏳ Step 4: View Results")
        
        st.markdown("---")
        
        # Display current selections
        if st.session_state.selected_benchmark:
            st.write(f"**Benchmark:** {st.session_state.selected_benchmark}")
        
        if st.session_state.selected_pagerank:
            st.write(f"**PageRank:** {st.session_state.selected_pagerank}")
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Reset Workflow", type="secondary"):
            reset_workflow()
            st.rerun()
    
    # Main content
    if st.session_state.step == 1:
        show_step1_benchmark_selection()
    elif st.session_state.step == 2:
        show_step2_pagerank_optimization()
    elif st.session_state.step == 3:
        show_step3_run_dreamplace()
    elif st.session_state.step == 4:
        show_step4_view_results()

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
        if st.button("➡️ Next: PageRank Optimization", type="primary"):
            st.session_state.step = 2
            st.rerun()

def show_step2_pagerank_optimization():
    """Step 2: Apply PageRank optimization."""
    st.markdown('<div class="step-header">Step 2: PageRank Optimization</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong></div>', unsafe_allow_html=True)
    
    st.write("Select a PageRank optimization strategy to reorder the placement file:")
    
    # PageRank options
    pagerank_options = {
        "Global (All Components)": {
            "script": "makePL.py",
            "description": "Sort all components by PageRank score",
            "icon": "🌐"
        },
        "Standard Cells Only": {
            "script": "makePL_stdcell.py",
            "description": "Sort only standard cells (area < 1000)",
            "icon": "📱"
        },
        "Macros Only": {
            "script": "makePL_macro.py",
            "description": "Sort only macro blocks (area ≥ 1000)",
            "icon": "📦"
        },
        "Fixed Components": {
            "script": "makePL_fixed.py",
            "description": "Sort only FIXED/terminal components",
            "icon": "📌"
        },
        "Movable Components": {
            "script": "makePL_movable.py",
            "description": "Sort only movable components",
            "icon": "🔄"
        }
    }
    
    # Display options
    for option_name, option_info in pagerank_options.items():
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"{option_info['icon']} **{option_name}**")
                st.caption(option_info['description'])
            
            with col2:
                if st.button(
                    "Select",
                    key=f"pr_{option_name}",
                    use_container_width=True,
                    type="primary" if st.session_state.selected_pagerank == option_name else "secondary"
                ):
                    st.session_state.selected_pagerank = option_name
    
    # Area threshold for macro/stdcell options
    if st.session_state.selected_pagerank in ["Standard Cells Only", "Macros Only"]:
        st.markdown("---")
        area_threshold = st.slider(
            "Area Threshold",
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            help="Components with area ≥ threshold are considered macros"
        )
    else:
        area_threshold = 1000
    
    # Execute button
    if st.session_state.selected_pagerank:
        st.markdown("---")
        st.markdown(f'<div class="success-box">✅ Selected: <strong>{st.session_state.selected_pagerank}</strong></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Benchmark Selection", type="secondary"):
                st.session_state.step = 1
                st.rerun()
        
        with col2:
            if st.button("🚀 Run PageRank Optimization", type="primary"):
                script_name = pagerank_options[st.session_state.selected_pagerank]["script"]
                
                st.info("🔄 Running PageRank optimization...")
                
                # Create container for real-time log
                log_container = st.container()
                with log_container:
                    st.subheader("📋 Execution Log")
                    log_output = st.empty()
                
                success, output = run_pagerank_script(
                    st.session_state.selected_benchmark,
                    script_name,
                    area_threshold,
                    log_output
                )
                
                if success:
                    st.success("✅ PageRank optimization completed!")
                    st.session_state.pagerank_completed = True
                    st.session_state.step = 3
                    st.rerun()
                else:
                    st.error(f"❌ PageRank optimization failed!")
                    st.error(output)

def show_step3_run_dreamplace():
    """Step 3: Run DREAMPlace."""
    st.markdown('<div class="step-header">Step 3: Run DREAMPlace</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-box">Benchmark: <strong>{st.session_state.selected_benchmark}</strong><br>PageRank: <strong>{st.session_state.selected_pagerank}</strong></div>', unsafe_allow_html=True)
    
    st.write("Click the button below to run DREAMPlace with the optimized placement file.")
    
    st.markdown('<div class="warning-box">⚠️ This process may take several minutes depending on the benchmark size.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("⬅️ Back to PageRank", type="secondary"):
            st.session_state.step = 2
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
    
    # Get latest plot image
    latest_image = get_latest_plot_image(st.session_state.selected_benchmark)
    
    if latest_image:
        st.subheader("📊 Final Placement Visualization")
        
        # Display image (rotated 180 degrees)
        rotated_img = rotate_image_180(latest_image)
        st.image(rotated_img, caption=f"Final placement: {os.path.basename(latest_image)}", use_container_width=True)
        
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
                                st.image(rotated_img, caption=os.path.basename(png_files[idx]), use_container_width=True)
    else:
        st.warning("⚠️ No visualization found. The plot directory may be empty.")
        st.write(f"Expected location: `{RESULTS_DIR}/{st.session_state.selected_benchmark}/plot`")
    
    st.markdown("---")
    
    # Action buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Start New Optimization", type="primary", use_container_width=True):
            reset_workflow()
            st.rerun()
    
    with col2:
        if st.button("📥 Download Results", type="secondary", use_container_width=True):
            st.info("Results are saved in the DREAMPlace results directory")
            st.code(f"{RESULTS_DIR}/{st.session_state.selected_benchmark}")

if __name__ == "__main__":
    main()
