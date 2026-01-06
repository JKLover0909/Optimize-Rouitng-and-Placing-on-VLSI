# Model Management in MaskPlace

## Overview
MaskPlace now includes automatic model management to keep only the best-performing checkpoints during training. This prevents storage overflow from hundreds of saved models.

## Features

### 1. Automatic Top-N Model Retention
During training, MaskPlace automatically keeps only the top N models by reward and deletes older, lower-performing checkpoints.

### 2. Configurable via Parameter
Use the `--keep_top_n` parameter to specify how many top models to retain:

```bash
# Keep only top 5 models (default)
python PPO2.py --benchmark adaptec1 --pnm 128 --keep_top_n 5

# Keep top 10 models
python PPO2.py --benchmark adaptec1 --pnm 128 --keep_top_n 10

# Disable automatic cleanup (keep all models)
python PPO2.py --benchmark adaptec1 --pnm 128 --keep_top_n 0
```

### 3. Smart Cleanup Logic
- Models are sorted by reward (higher is better)
- Only models for the same benchmark and pnm configuration are compared
- Cleanup happens automatically after each successful save
- Deletion messages are printed to console

## Model Filename Format
Models are saved with the following naming convention:
```
net_dict-{benchmark}-{pnm}-{timestamp}-{reward}.pkl
```

Example:
```
net_dict-adaptec1-128-2025-12-16-11-56-28-14884.pkl
                     └─────┬─────┘ └─────┬─────┘ └──┬──┘
                        Timestamp          Date   Reward
```

## Manual Cleanup Script
For existing models, use the manual cleanup script:

```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace
./cleanup_models.sh
```

This script will:
1. List all saved models sorted by reward
2. Show which models will be kept and deleted
3. Ask for confirmation before deleting
4. Default: keep top 5 models

## Example Usage

### Training with Auto-Cleanup
```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace

# Run inside Docker with top-5 retention
./run_maskplace_custom.sh \
  --benchmark adaptec1 \
  --ordering pagerank \
  --pnm 128 \
  --lr 0.001 \
  --seed 42
```

The `run_maskplace_custom.sh` script uses `--keep_top_n 5` by default.

### Loading Best Model for Testing
After training, load the best checkpoint:

```bash
# Find best model
ls -lh save_models/net_dict-adaptec1-128-*.pkl | sort -k5 -rn | head -1

# Test with best model
python PPO2.py \
  --benchmark adaptec1 \
  --pnm 128 \
  --is_test \
  --model_path ./save_models/net_dict-adaptec1-128-2025-12-15-04-02-10-100024.pkl
```

## Technical Details

### Implementation
The cleanup logic is implemented in `PPO2.py`:

1. **save_param()** method (lines 232-254):
   - Saves model with metadata (reward, benchmark, pnm)
   - Calls cleanup after successful save
   - Only runs cleanup if `keep_top_n > 0`

2. **_cleanup_old_models()** method (lines 256-291):
   - Uses glob pattern to find matching models
   - Parses reward from filename
   - Sorts by reward descending
   - Keeps top N, deletes rest
   - Prints deletion confirmations

### Storage Location
Models are saved in:
```
/home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace/maskplace/save_models/
```

### Model Contents
Each `.pkl` file contains:
- `actor_net_dict`: Actor network state dict
- `critic_net_dict`: Critic network state dict
- `reward`: Achieved reward
- `benchmark`: Benchmark name
- `pnm`: Number of placed macros

## Best Practices

1. **Keep top 5-10 models** for most use cases
2. **Set keep_top_n=0** if you need to preserve all checkpoints for analysis
3. **Use manual cleanup** to clean up existing models from previous runs
4. **Monitor console output** during training to see which models are deleted
5. **Always note the best model filename** before stopping training

## Integration with Centrality Ordering

The model management works seamlessly with all ordering methods:

```bash
# Default ordering + top 5 models
./run_maskplace_custom.sh --benchmark adaptec1 --ordering default --pnm 128

# PageRank ordering + top 5 models
./run_maskplace_custom.sh --benchmark adaptec1 --ordering pagerank --pnm 128 \
  --centrality-file ../src/centrality_adaptec1.pkl

# Eigenvector ordering + top 5 models
./run_maskplace_custom.sh --benchmark adaptec1 --ordering eigenvector --pnm 128 \
  --centrality-file ../src/centrality_adaptec1.pkl

# Degree ordering + top 5 models
./run_maskplace_custom.sh --benchmark adaptec1 --ordering degree --pnm 128 \
  --centrality-file ../src/centrality_adaptec1.pkl
```

## Troubleshooting

### Issue: Models not being cleaned up
**Solution**: Check that `--keep_top_n` is set to a positive value (default is 5)

### Issue: All models deleted
**Solution**: Ensure multiple models exist before cleanup runs. First model is never deleted.

### Issue: Cannot find best model
**Solution**: Use the list_models.sh script to see all models sorted by reward:
```bash
cd /home/ubuntu/vnet/Optimize-Rouitng-and-Placing-on-VLSI/Thesis/MaskPlace
./list_models.sh
```

## References
- Main implementation: `MaskPlace/maskplace/PPO2.py`
- Manual cleanup: `MaskPlace/cleanup_models.sh`
- Model listing: `MaskPlace/list_models.sh`
- Centrality usage: `MASKPLACE_CENTRALITY_USAGE.md`
