# MaskPlace với Centrality-based Ordering

## Tổng quan

MaskPlace đã được cập nhật để hỗ trợ 4 phương pháp sắp xếp thứ tự đặt macro:

1. **default** (topology) - Phương pháp topology gốc của MaskPlace
2. **pagerank** - Sắp xếp theo PageRank centrality
3. **eigenvector** - Sắp xếp theo Eigenvector centrality  
4. **degree** - Sắp xếp theo Degree centrality

## Cách sử dụng

### Bước 0: Khởi động Docker container

MaskPlace phải chạy trong Docker container:

```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace

# Lần đầu tiên: Build image (chỉ làm 1 lần)
bash build-maskplace-image.sh

# Tạo và khởi động container
bash docker-run-maskplace.sh run

# Các lần sau: Chỉ cần start container
bash docker-run-maskplace.sh start

# Kiểm tra container đang chạy
bash docker-run-maskplace.sh status
```

### Bước 1: Tính toán centrality scores (tùy chọn)

Có thể tính toán trước để tăng tốc độ. **Chạy trong container**:

```bash
# Vào container
docker attach maskplace_dev

# Hoặc exec từ host
docker exec -it maskplace_dev bash

# Trong container, chạy compute_centrality
cd /MaskPlace  # hoặc wherever your src is mounted
python compute_centrality.py \
    --nodes /DREAMPlace/install/benchmarks/ispd2005/adaptec1/adaptec1.nodes \
    --nets /DREAMPlace/install/benchmarks/ispd2005/adaptec1/adaptec1.nets \
    --output /DREAMPlace/install/benchmarks/ispd2005/adaptec1/adaptec1_centrality.pkl
```

### Bước 2: Chạy MaskPlace với phương pháp khác nhau

#### Cách 1: Sử dụng script tiện ích (khuyến nghị):

```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace

# Phương pháp default (topology gốc)
bash run_maskplace_custom.sh --benchmark adaptec1 --ordering default

# Phương pháp PageRank
bash run_maskplace_custom.sh --benchmark adaptec1 --ordering pagerank

# Phương pháp Eigenvector
bash run_maskplace_custom.sh --benchmark adaptec1 --ordering eigenvector

# Phương pháp Degree
bash run_maskplace_custom.sh --benchmark adaptec1 --ordering degree

# Với file centrality đã tính trước (đường dẫn trong container)
bash run_maskplace_custom.sh \
    --benchmark adaptec1 \
    --ordering pagerank \
    --centrality-file /DREAMPlace/install/benchmarks/ispd2005/adaptec1/adaptec1_centrality.pkl
```

#### Cách 2: Chạy trực tiếp trong container:

```bash
# Vào container
docker attach maskplace_dev

# Trong container
cd /MaskPlace/maskplace

# Default (topology)
python PPO2.py --benchmark adaptec1 --ordering_method default

# PageRank
python PPO2.py --benchmark adaptec1 --ordering_method pagerank

# Eigenvector
python PPO2.py --benchmark adaptec1 --ordering_method eigenvector

# Degree
python PPO2.py --benchmark adaptec1 --ordering_method degree

# Với centrality file
python PPO2.py \
    --benchmark adaptec1 \
    --ordering_method pagerank \
    --centrality_file /DREAMPlace/install/benchmarks/ispd2005/adaptec1/adaptec1_centrality.pkl
```

## Tham số bổ sung

```bash
--pnm NUM              # Số lượng macro cần đặt (default: 128)
--lr LEARNING_RATE     # Learning rate (default: 0.0025)
--seed SEED            # Random seed (default: 42)
--batch_size SIZE      # Batch size (default: 64)
```

## Ví dụ so sánh các phương pháp

```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace

# Đảm bảo container đang chạy
bash docker-run-maskplace.sh status

# So sánh 4 phương pháp với cùng seed
for method in default pagerank eigenvector degree; do
    echo "Testing $method..."
    bash run_maskplace_custom.sh \
        --benchmark adaptec1 \
        --ordering $method \
        --seed 42 \
        --pnm 128
done
```

## Lưu ý

- Nếu không có file centrality, hệ thống sẽ tính toán on-the-fly bằng NetworkX
- Phương pháp `default` tương đương với MaskPlace gốc (topology-based)
- PageRank và Eigenvector có thể cho kết quả tốt hơn cho mạch có cấu trúc phân cấp
- Degree centrality nhanh nhất nhưng đơn giản nhất
