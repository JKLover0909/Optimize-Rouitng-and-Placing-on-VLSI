#!/usr/bin/env python3
"""
DREAMPlace Console App - Interactive Terminal Interface
A complete workflow for IC placement optimization with PageRank
"""

import subprocess
import os
import glob
import shutil
import sys
from pathlib import Path

# Configuration
BASE_DIR = "DREAMPlace/install"
BENCHMARKS_DIR = f"{BASE_DIR}/benchmarks/ispd2005"
RESULTS_DIR = f"{BASE_DIR}/results"
SCRIPTS_DIR = "."

# Color codes for terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Print header with color."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_info(text):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')

def pause():
    """Pause and wait for user input."""
    input(f"\n{Colors.OKBLUE}Press Enter to continue...{Colors.ENDC}")

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
        print_success(f"Original .pl file backed up to: {backup_file}")
        return True
    elif os.path.exists(backup_file):
        print_info("Original .pl backup already exists")
        return True
    return False

def restore_original_pl(benchmark):
    """Restore original .pl file from backup."""
    pl_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.pl"
    backup_file = f"{pl_file}.original"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, pl_file)
        print_success(f"Restored original .pl file")
        return True
    else:
        print_warning("No backup file found to restore")
        return False

def get_benchmark_info(benchmark):
    """Get information about the benchmark."""
    nodes_file = f"{BENCHMARKS_DIR}/{benchmark}/{benchmark}.nodes"
    
    if os.path.exists(nodes_file):
        with open(nodes_file, 'r') as f:
            for line in f:
                if 'NumNodes' in line:
                    return line.strip()
    return "Info not available"

def select_benchmark():
    """Step 1: Select benchmark from ISPD2005."""
    clear_screen()
    print_header("STEP 1: SELECT BENCHMARK (ISPD2005)")
    
    benchmarks = get_available_benchmarks()
    
    if not benchmarks:
        print_error("No benchmarks found in the ISPD2005 directory!")
        print_info(f"Expected location: {BENCHMARKS_DIR}")
        pause()
        return None
    
    print(f"Found {Colors.BOLD}{len(benchmarks)}{Colors.ENDC} benchmarks:\n")
    
    # Display benchmarks in columns
    for idx, benchmark in enumerate(benchmarks, 1):
        print(f"  {Colors.OKGREEN}{idx:2d}.{Colors.ENDC} {benchmark}")
    
    print(f"\n  {Colors.WARNING}0.{Colors.ENDC} Back to main menu")
    
    while True:
        try:
            choice = input(f"\n{Colors.BOLD}Select benchmark (number): {Colors.ENDC}").strip()
            
            if choice == '0':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(benchmarks):
                selected = benchmarks[choice_num - 1]
                
                print(f"\n{Colors.OKGREEN}Selected: {Colors.BOLD}{selected}{Colors.ENDC}")
                print_info(get_benchmark_info(selected))
                
                # Backup original
                backup_original_pl(selected)
                
                pause()
                return selected
            else:
                print_error("Invalid choice. Please try again.")
        except ValueError:
            print_error("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\n")
            return None

def select_pagerank_option():
    """Step 2: Select PageRank optimization strategy."""
    clear_screen()
    print_header("STEP 2: PAGERANK OPTIMIZATION")
    
    pagerank_options = [
        {
            "name": "Global (All Components)",
            "script": "makePL.py",
            "description": "Sort all components by PageRank score",
            "icon": "🌐",
            "needs_threshold": False
        },
        {
            "name": "Standard Cells Only",
            "script": "makePL_stdcell.py",
            "description": "Sort only standard cells (area < threshold)",
            "icon": "📱",
            "needs_threshold": True
        },
        {
            "name": "Macros Only",
            "script": "makePL_macro.py",
            "description": "Sort only macro blocks (area ≥ threshold)",
            "icon": "📦",
            "needs_threshold": True
        },
        {
            "name": "Fixed Components",
            "script": "makePL_fixed.py",
            "description": "Sort only FIXED/terminal components",
            "icon": "📌",
            "needs_threshold": False
        },
        {
            "name": "Movable Components",
            "script": "makePL_movable.py",
            "description": "Sort only movable components",
            "icon": "🔄",
            "needs_threshold": False
        }
    ]
    
    print("Select a PageRank optimization strategy:\n")
    
    for idx, option in enumerate(pagerank_options, 1):
        print(f"  {Colors.OKGREEN}{idx}.{Colors.ENDC} {option['icon']} {Colors.BOLD}{option['name']}{Colors.ENDC}")
        print(f"     {Colors.OKCYAN}{option['description']}{Colors.ENDC}")
        print()
    
    print(f"  {Colors.WARNING}0.{Colors.ENDC} Back to benchmark selection")
    
    while True:
        try:
            choice = input(f"\n{Colors.BOLD}Select option (number): {Colors.ENDC}").strip()
            
            if choice == '0':
                return None, None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(pagerank_options):
                selected_option = pagerank_options[choice_num - 1]
                
                # Get area threshold if needed
                area_threshold = 1000
                if selected_option['needs_threshold']:
                    print(f"\n{Colors.OKCYAN}Area threshold (components with area ≥ threshold are macros){Colors.ENDC}")
                    threshold_input = input(f"Enter threshold [default=1000]: ").strip()
                    if threshold_input:
                        try:
                            area_threshold = int(threshold_input)
                        except ValueError:
                            print_warning("Invalid threshold, using default: 1000")
                            area_threshold = 1000
                
                return selected_option, area_threshold
            else:
                print_error("Invalid choice. Please try again.")
        except ValueError:
            print_error("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\n")
            return None, None

def run_pagerank_optimization(benchmark, pagerank_option, area_threshold):
    """Execute PageRank optimization."""
    clear_screen()
    print_header("RUNNING PAGERANK OPTIMIZATION")
    
    print(f"Benchmark: {Colors.BOLD}{benchmark}{Colors.ENDC}")
    print(f"Strategy:  {Colors.BOLD}{pagerank_option['name']}{Colors.ENDC}")
    if pagerank_option['needs_threshold']:
        print(f"Threshold: {Colors.BOLD}{area_threshold}{Colors.ENDC}")
    print()
    
    script_path = f"{SCRIPTS_DIR}/{pagerank_option['script']}"
    
    if not os.path.exists(script_path):
        print_error(f"Script not found: {script_path}")
        pause()
        return False
    
    # Restore original .pl before running PageRank
    print_info("Restoring original .pl file...")
    restore_original_pl(benchmark)
    
    print_info(f"Running {pagerank_option['script']}...")
    print(f"{Colors.OKCYAN}{'─'*60}{Colors.ENDC}\n")
    
    try:
        # Build command
        if pagerank_option['needs_threshold']:
            cmd = ['python3', script_path, benchmark, str(area_threshold)]
        else:
            cmd = ['python3', script_path, benchmark]
        
        # Run the script with real-time output
        process = subprocess.Popen(
            cmd,
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        print(f"\n{Colors.OKCYAN}{'─'*60}{Colors.ENDC}\n")
        
        if process.returncode == 0:
            print_success("PageRank optimization completed successfully!")
            pause()
            return True
        else:
            print_error("PageRank optimization failed!")
            pause()
            return False
            
    except Exception as e:
        print_error(f"Error running PageRank: {str(e)}")
        pause()
        return False

def run_dreamplace(benchmark):
    """Step 3: Run DREAMPlace."""
    clear_screen()
    print_header("STEP 3: RUNNING DREAMPLACE")
    
    print(f"Benchmark: {Colors.BOLD}{benchmark}{Colors.ENDC}\n")
    
    script_path = f"{SCRIPTS_DIR}/run_dreamplace.sh"
    
    if not os.path.exists(script_path):
        print_error(f"Script not found: {script_path}")
        pause()
        return False
    
    print_warning("This process may take several minutes...")
    print_info("Starting DREAMPlace...")
    print(f"{Colors.OKCYAN}{'─'*60}{Colors.ENDC}\n")
    
    try:
        # Run DREAMPlace with real-time output
        process = subprocess.Popen(
            ['bash', script_path, benchmark],
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        print(f"\n{Colors.OKCYAN}{'─'*60}{Colors.ENDC}\n")
        
        if process.returncode == 0:
            print_success("DREAMPlace completed successfully!")
            pause()
            return True
        else:
            print_error("DREAMPlace execution failed!")
            pause()
            return False
            
    except Exception as e:
        print_error(f"Error running DREAMPlace: {str(e)}")
        pause()
        return False

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
        try:
            num_str = filename.replace('iter', '').replace('.png', '')
            return int(num_str)
        except:
            return -1
    
    latest_file = max(png_files, key=get_iter_number)
    return latest_file

def view_results(benchmark):
    """Step 4: View results."""
    clear_screen()
    print_header("STEP 4: RESULTS & VISUALIZATION")
    
    print(f"Benchmark: {Colors.BOLD}{benchmark}{Colors.ENDC}\n")
    
    # Get latest plot image
    latest_image = get_latest_plot_image(benchmark)
    
    if latest_image:
        print_success(f"Latest visualization: {os.path.basename(latest_image)}")
        print_info(f"Full path: {latest_image}")
        print()
        
        # Results directory
        results_path = f"{RESULTS_DIR}/{benchmark}"
        print(f"Results directory: {Colors.OKCYAN}{results_path}{Colors.ENDC}")
        
        # Count plots
        plot_dir = f"{results_path}/plot"
        if os.path.exists(plot_dir):
            png_files = glob.glob(f"{plot_dir}/iter*.png")
            print(f"Total iterations: {Colors.BOLD}{len(png_files)}{Colors.ENDC}")
        
        print()
        print_info("You can view the images using:")
        print(f"  - Image viewer: xdg-open {latest_image}")
        print(f"  - VS Code: code {latest_image}")
        print(f"  - Directory: ls -lh {plot_dir}")
        
    else:
        print_warning("No visualization found.")
        print_info(f"Expected location: {RESULTS_DIR}/{benchmark}/plot")
    
    print()
    pause()

def run_complete_workflow():
    """Run the complete 4-step workflow."""
    # Step 1: Select benchmark
    benchmark = select_benchmark()
    if not benchmark:
        return
    
    # Step 2: Select PageRank option
    pagerank_option, area_threshold = select_pagerank_option()
    if not pagerank_option:
        return
    
    # Run PageRank optimization
    success = run_pagerank_optimization(benchmark, pagerank_option, area_threshold)
    if not success:
        print_error("PageRank optimization failed. Aborting workflow.")
        pause()
        return
    
    # Step 3: Run DREAMPlace
    success = run_dreamplace(benchmark)
    if not success:
        print_error("DREAMPlace execution failed. Aborting workflow.")
        pause()
        return
    
    # Step 4: View results
    view_results(benchmark)
    
    print_success("Workflow completed successfully!")
    pause()

def main_menu():
    """Display main menu."""
    while True:
        clear_screen()
        print_header("DREAMPLACE + PAGERANK OPTIMIZER")
        
        print(f"{Colors.BOLD}Main Menu:{Colors.ENDC}\n")
        print(f"  {Colors.OKGREEN}1.{Colors.ENDC} 🚀 Run Complete Workflow (Recommended)")
        print(f"     {Colors.OKCYAN}All 4 steps: Benchmark → PageRank → DREAMPlace → Results{Colors.ENDC}")
        print()
        print(f"  {Colors.OKGREEN}2.{Colors.ENDC} 📊 Quick Run (Select Benchmark + Run DREAMPlace)")
        print(f"     {Colors.OKCYAN}Skip PageRank optimization, use existing .pl file{Colors.ENDC}")
        print()
        print(f"  {Colors.OKGREEN}3.{Colors.ENDC} 🔧 Advanced Options")
        print(f"     {Colors.OKCYAN}Run individual steps separately{Colors.ENDC}")
        print()
        print(f"  {Colors.WARNING}0.{Colors.ENDC} ❌ Exit")
        
        choice = input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}").strip()
        
        if choice == '1':
            run_complete_workflow()
        elif choice == '2':
            benchmark = select_benchmark()
            if benchmark:
                if run_dreamplace(benchmark):
                    view_results(benchmark)
        elif choice == '3':
            advanced_menu()
        elif choice == '0':
            clear_screen()
            print(f"{Colors.OKGREEN}Thank you for using DREAMPlace Optimizer!{Colors.ENDC}\n")
            sys.exit(0)
        else:
            print_error("Invalid choice. Please try again.")
            pause()

def advanced_menu():
    """Advanced options menu."""
    while True:
        clear_screen()
        print_header("ADVANCED OPTIONS")
        
        print(f"{Colors.BOLD}Select operation:{Colors.ENDC}\n")
        print(f"  {Colors.OKGREEN}1.{Colors.ENDC} Select Benchmark Only")
        print(f"  {Colors.OKGREEN}2.{Colors.ENDC} Run PageRank Optimization")
        print(f"  {Colors.OKGREEN}3.{Colors.ENDC} Run DREAMPlace")
        print(f"  {Colors.OKGREEN}4.{Colors.ENDC} View Results")
        print(f"  {Colors.OKGREEN}5.{Colors.ENDC} Restore Original .pl File")
        print()
        print(f"  {Colors.WARNING}0.{Colors.ENDC} Back to Main Menu")
        
        choice = input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}").strip()
        
        if choice == '1':
            select_benchmark()
        elif choice == '2':
            benchmark = select_benchmark()
            if benchmark:
                pagerank_option, area_threshold = select_pagerank_option()
                if pagerank_option:
                    run_pagerank_optimization(benchmark, pagerank_option, area_threshold)
        elif choice == '3':
            benchmark = select_benchmark()
            if benchmark:
                run_dreamplace(benchmark)
        elif choice == '4':
            benchmark = select_benchmark()
            if benchmark:
                view_results(benchmark)
        elif choice == '5':
            benchmark = select_benchmark()
            if benchmark:
                restore_original_pl(benchmark)
                pause()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice. Please try again.")
            pause()

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{Colors.WARNING}Operation cancelled by user.{Colors.ENDC}\n")
        sys.exit(0)
