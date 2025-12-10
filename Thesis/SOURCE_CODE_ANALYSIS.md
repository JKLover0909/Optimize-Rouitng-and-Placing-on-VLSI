# VLSI Placement Optimization + Routing Analysis - Source Code Analysis

Tieng anh

## 🏗️ Overall Architecture

Dự án này là một **hệ thống tối ưu hóa vị trí thành phần (placement) trong thiết kế vi mạch VLSI** kết hợp với **phân tích và trực quan hóa kết quả định tuyến (routing)**.

Quy trình làm việc:
```
Input (Benchmark) 
    ↓
[PageRank Optimization] → Reorder .pl file based on importance
    ↓
[DREAMPlace] → Optimize physical placement using neural networks
    ↓
[Routing Visualization] → Analyze and visualize routing results
```

---

## 📁 Project Structure

### **Top-Level Scripts** (Python Scripts chính)

| File | Purpose | Type |
|------|---------|------|
| `dreamplace_console.py` | 🎯 **Interactive CLI for complete workflow** | Menu Interface |
| `dreamplace_gui.py` | GUI interface (Streamlit) | Web UI |
| `makePL_macro.py` | Reorder .pl file - MACRO only | PageRank |
| `makePL_stdcell.py` | Reorder .pl file - Standard cells only | PageRank |
| `makePL_fixed.py` | Reorder .pl file - Fixed/terminal components | PageRank |
| `makePL_movable.py` | Reorder .pl file - Movable components | PageRank |
| `makePL.py` | Reorder .pl file - ALL components | PageRank |
| `makegraph_macro.py` | Calculate PageRank for macros | Graph Analysis |
| `makegraph.py` | Calculate PageRank for all components | Graph Analysis |
| `visualize_routing.py` | Create visualizations of routing results | Visualization |
| `Placement_to_routing_converter.py` | Convert placement to routing format | Conversion |
| `run_dreamplace.sh` | Shell script to execute DREAMPlace in Docker | Orchestration |

---

## 🔍 Detailed Component Analysis

### 1. **dreamplace_console.py** (549 lines) - Main Interactive Interface

**Mục đích**: Cung cấp menu tương tác để chạy toàn bộ workflow từ A-Z

**Các hàm chính**:

```python
def main_menu()                          # Menu chính với 3 tùy chọn
def run_complete_workflow()              # Chạy quy trình 4 bước đầy đủ
def select_benchmark()                   # Bước 1: Chọn benchmark (adaptec1, bigblue1, ...)
def select_pagerank_option()             # Bước 2: Chọn strategy PageRank
def run_pagerank_optimization()          # Thực thi script PageRank
def run_dreamplace()                     # Bước 3: Chạy DREAMPlace (GPU-optimized placement)
def view_results()                       # Bước 4: Xem kết quả
def advanced_menu()                      # Menu nâng cao cho các tùy chọn riêng lẻ
def backup_original_pl()                 # Backup file .pl gốc
def restore_original_pl()                # Khôi phục file .pl gốc
```

**Workflow Bước 1-4**:
1. Chọn benchmark (e.g., adaptec1, bigblue1)
2. Chọn strategy tối ưu hóa PageRank (global, macros only, std cells only, v.v.)
3. Chạy DREAMPlace để tối ưu vị trí thành phần
4. Xem kết quả visualizations

---

### 2. **makePL_macro.py** (258 lines) - PageRank for Macros

**Mục đích**: Xắp xếp lại file .pl sao cho các macro components (large components) được sắp xếp theo thứ tự PageRank

**Các hàm chính**:

```python
def parse_nodes_file()                   # Đọc file .nodes (kích thước thành phần)
def identify_macros()                    # Xác định macro dựa trên area threshold
def parse_nets_file()                    # Đọc file .nets (kết nối hypergraph)
def build_macro_graph()                  # Xây dựng directed graph macro-to-macro
def calculate_pagerank()                 # Tính PageRank cho từng macro
def parse_pl_file()                      # Đọc file .pl (vị trí hiện tại)
def write_pl_file()                      # Ghi file .pl lại (reordered)
```

**Quy trình**:

```
1. Parse .nodes → Tính area của từng component
2. Identify macros → Các component có area ≥ threshold (default: 1000)
3. Parse .nets → Trích xuất kết nối giữa các component
4. Build macro-only graph → Chỉ lấy cạnh giữa macro-to-macro
5. Calculate PageRank → Tính điểm quan trọng cho mỗi macro
6. Reorder .pl → Macro được sắp xếp theo PageRank (cao → thấp), std cells ở cuối
7. Write updated .pl file
```

**Ví dụ output**:
```
Benchmark: adaptec1
Area threshold: 1000

Step 1: Parsing .nodes file...
  Total components: 50000
  Identified macros: 12

Step 5: Calculating PageRank...
  Top 5 macros by PageRank:
    1. mem_block_0: 0.15234567
    2. controller_1: 0.12456789
    3. ...
```

---

### 3. **makegraph_macro.py** (340 lines) - PageRank Calculation (Detailed)

**Mục đích**: Tính toán PageRank chi tiết cho các macro blocks

**Các hàm chính**:

```python
def parse_nodes_file()                   # Parse .nodes
def identify_macros()                    # Xác định macros
def parse_nets_file()                    # Parse .nets (structured)
def build_macro_graph()                  # Xây dựng directed graph
def calculate_pagerank()                 # Tính PageRank với damping factor
def main()                               # CLI tool
```

**Key Features**:
- Hỗ trợ CLI arguments: `--threshold`, `--damping`, `--output`
- Tính số macro connections
- Output file: `<benchmark>_macro_result.txt` với ranking chi tiết
- Placement suggestions: HIGH PRIORITY (center), MEDIUM (middle), LOW (edges)

**Ví dụ**:
```bash
python makegraph_macro.py DREAMPlace/install/benchmarks/ispd2005/adaptec1 \
    --threshold 1000 --damping 0.85 --output adaptec1_macro_result.txt
```

---

### 4. **visualize_routing.py** (475 lines) - Routing Visualization

**Mục đích**: Trực quan hóa kết quả routing từ NTHU-Route

**Các hàm chính**:

```python
def parse_routing_output()               # Parse output file của NTHU-Route
def get_grid_bounds()                    # Tính giới hạn grid
def visualize_routing_layer()            # Vẽ routing trên từng layer
def create_congestion_heatmap()          # Tạo heatmap mật độ routing
def visualize_3d_overview()              # Tạo 3D overview
def main()                               # CLI tool
```

**Supported Formats**:
- Input: NTHU-Route output (ISPD 2008 format)
- Format: `(x1,y1,z1)-(x2,y2,z2)` (3D coordinates)

**Output Files**:
- `routing_layer<N>.png` - Routing visualization trên layer N
- `congestion_heatmap.png` - Density map
- `routing_3d_overview.png` - 3D visualization

**CLI Usage**:
```bash
python visualize_routing.py <routing_output_file> --heatmap-only --output-dir ./results
```

---

### 5. **Placement_to_routing_converter.py** (602 lines) - Format Conversion

**Mục đích**: Chuyển đổi file placement (.pl) sang format routing (ISPD benchmark)

**Class chính**: `RoutingBenchmarkGenerator`

**Các method chính**:

```python
def process_scl_file()                   # Đọc file SCL (row definitions)
def process_nodes_file()                 # Đọc file NODES
def process_nets_file()                  # Đọc file NETS
def process_placement_file()             # Đọc file PL (placement)
def generate_def_file()                  # Sinh file DEF (routing format)
```

**Quy trình**:
```
Input Files (Bookshelf format):
  - .scl (row definitions)
  - .nodes (component definitions)
  - .nets (net connectivity)
  - .pl (placement coordinates)
        ↓
Processing:
  - Parse rows, cells, nets
  - Extract pin positions
  - Calculate routing capacity
        ↓
Output:
  - DEF file (ISPD routing format)
  - GR file (detailed routing format)
```

---

### 6. **run_dreamplace.sh** - Docker Orchestration

**Mục đích**: Chạy DREAMPlace placement optimizer trong Docker container

**Quy trình**:
```bash
docker exec dreamplace_dev python dreamplace/Placer.py \
    test/ispd2005/<benchmark>.json \
    --max-iter 1000 \
    --output-place <benchmark>_placed.pl
```

---

## 🧠 Algorithm Details

### **PageRank Algorithm**

**Công thức cơ bản**:
```
PR(A) = (1-d)/N + d * Σ(PR(T) / C(T))
```
Trong đó:
- `d` = damping factor (thường 0.85)
- `N` = số nodes
- `T` = các node pointing tới A
- `C(T)` = out-degree của T

**Graph Construction**:
1. Nodes = Thành phần (macros hoặc tất cả)
2. Edges = Kết nối giữa thành phần thông qua nets
3. Weight = Số nets kết nối (multi-edges được weight)

**Ứng dụng**:
- Macros có PageRank cao → Placed ở **center** (minimize delay)
- Macros có PageRank thấp → Placed ở **edges** (reduce congestion)

---

## 📊 File Format Reference

### **.nodes File** (Bookshelf)
```
UCLA nodes 1.0
NumNodes : 50000
NumTerminals : 100

io0          10.0    20.0
mem_block_0  100.0   150.0
std_cell_1   1.0     2.0
# terminal pins
io1          10.0    10.0    terminal
```

### **.nets File** (Hypergraph)
```
UCLA nets 1.0
NumNets : 5000

NetDegree : 5
pin0      I
pin1      O
pin2      I
pin3      B

NetDegree : 3
io0       O
mem0      I
ctrl0     B
```

### **.pl File** (Placement)
```
UCLA pl 1.0

io0       100.0    200.0    : N
mem_block_0  500.0  800.0   : N /FIXED
std_cell_1   150.0  250.0   : W
```

### **Routing Output** (NTHU-Route 3D format)
```
net0 0
(10,20,0)-(10,30,0)
(10,30,0)-(20,30,0)
(20,30,0)-(20,30,1)
!

net1 1
(15,25,1)-(25,25,1)
...
```

---

## 🔗 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ISPD2005 Benchmark                       │
│  (adaptec1, bigblue1, ...)                                 │
│  Files: .nodes, .nets, .scl, .pl                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  1. dreamplace_console.py    │
        │  (Interactive CLI)           │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  2. PageRank Optimization   │
        │  (makePL_*.py)              │
        │  - Graph building           │
        │  - PageRank calculation     │
        │  - .pl reordering           │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  3. DREAMPlace Placement    │
        │  (GPU-optimized)            │
        │  - run_dreamplace.sh        │
        │  - Neural network based     │
        │  - Output: Optimized .pl    │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  4. Routing (NTHU-Route)    │
        │  Input: Optimized .pl       │
        │  Output: .gr file (routing) │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  5. Visualization           │
        │  visualize_routing.py       │
        │  - Layer visualizations     │
        │  - Heatmaps                 │
        │  - 3D overviews             │
        └──────────────────────────────┘
```

---

## 💾 Key Data Structures

### **Graph Representation**
```python
G = nx.DiGraph()  # Directed graph

# Nodes
G.add_node(macro_name)

# Edges (with weights)
G.add_edge(driver, sink, weight=count, nets=[net_ids])
```

### **Placement Data**
```python
placement = {
    'node': 'mem_block_0',
    'x': 500.0,
    'y': 800.0,
    'orientation': 'N',
    'fixed': False
}
```

### **Routing Segment**
```python
segment = {
    'p1': (x1, y1, z1),
    'p2': (x2, y2, z2),
    'net': 'net_0'
}
```

---

## 🎯 Key Insights & Optimizations

### **1. Component Categorization**
- **Macros** (area ≥ 1000): Memory blocks, controllers → Optimize position
- **Standard Cells** (area < 1000): Logic cells → Keep in natural clusters
- **Fixed/Terminals**: I/O pins → Cannot move

### **2. PageRank Benefits**
- Highly connected components get higher scores
- Placement near center reduces interconnect delay
- Improves chip performance and power efficiency

### **3. Visualization Features**
- **Layer-by-layer visualization** → Identify congestion
- **Heatmaps** → Show routing bottlenecks
- **3D overview** → Global routing analysis

### **4. Docker Integration**
- All operations run in isolated Docker container
- GPU support for DREAMPlace acceleration
- Reproducible environment

---

## 🚀 Typical Workflow Example

```bash
# 1. Start Docker container
docker run --gpus all -it --name dreamplace_dev \
    -v "$(pwd)":/DREAMPlace limbo018/dreamplace:cuda bash

# 2. Inside container, run console
python3 dreamplace_console.py

# 3. Select benchmark: adaptec1
# 4. Select strategy: Macros Only
# 5. Set threshold: 1000
# 6. System runs:
#    - makePL_macro.py adaptec1 1000
#    - run_dreamplace.sh adaptec1
# 7. View results in DREAMPlace/install/results/adaptec1/plot/

# 8. (Optional) Visualize routing
python visualize_routing.py routing_output.gr --output-dir ./viz
```

---

## 📈 Performance Metrics

**Tracked in Results**:
- **Placement Quality**: Total wire length, HPWL (Half-Perimeter Wire Length)
- **Routing Quality**: Via count, congestion levels
- **Time**: Placement time, routing time
- **Convergence**: Iteration count for DREAMPlace

---

## 🔧 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **CLI** | Python 3 + Click/Argparse | Menu interfaces |
| **Graph** | NetworkX | PageRank calculation |
| **Visualization** | Matplotlib + NumPy | Plotting & heatmaps |
| **Placement** | DREAMPlace (GPU) | Neural network based |
| **Routing** | NTHU-Route | Detailed routing |
| **Orchestration** | Bash + Docker | Environment management |

---

## 🎓 Machine Learning in DREAMPlace

DREAMPlace uses **Neural Networks** for placement:
- Models the placement problem as an optimization task
- Uses gradient-based optimization
- GPU acceleration for speed
- Typically converges in 1000 iterations

---

## 📝 Summary

Dự án này là một **complete end-to-end VLSI optimization framework**:

1. **Input**: Benchmark netlists (nodes, nets, placement)
2. **Analysis**: PageRank importance calculation
3. **Optimization**: Neural network-based placement (DREAMPlace)
4. **Routing**: Global and detailed routing (NTHU-Route)
5. **Analysis**: Routing visualization and statistics

Tất cả các bước được tích hợp trong một interactive console application cho phép người dùng dễ dàng chạy complete workflow hoặc các bước riêng lẻ.

---

*Last updated: December 9, 2025*
