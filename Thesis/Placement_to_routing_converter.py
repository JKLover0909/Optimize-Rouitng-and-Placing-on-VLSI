import math
import sys
from collections import defaultdict
import os


class RoutingBenchmarkGenerator:
    def __init__(self):
        self.DEFAULT_ROW_HEIGHT = 12
        self.DEFAULT_PIN_METAL_LAYER = 1
        self.DEFAULT_WIRE_MINIMUM_WIDTH = 1
        self.FANOUT_CLIP_THRESHOLD = 1000

        # Database structures
        self.ObjectDB = {}
        self.NetDB = {}
        self.NetPinDB = {}
        self.CapAdjustmentDB = {}

        self.RowDB = []  # row_y_low values
        self.RowDBstartX = []  # starting X coordinates
        self.RowDBendX = []  # ending X coordinates

        # Index constants
        self.DXINDEX = 0
        self.DYINDEX = 1
        self.LOCXINDEX = 2
        self.LOCYINDEX = 3
        self.TYPEINDEX = 4

        # Window boundaries
        self.WINDOW_LX = 100000000
        self.WINDOW_LY = 100000000
        self.WINDOW_HX = -100000000
        self.WINDOW_HY = -100000000

    def my_max(self, x, y):
        return x if x > y else y

    def my_min(self, x, y):
        return x if x < y else y

    def is_odd(self, num):
        return num % 2 != 0

    def is_large_macro(self, dx, dy):
        LARGE_THRESHOLD = self.DEFAULT_ROW_HEIGHT * 3
        return dx > LARGE_THRESHOLD or dy > LARGE_THRESHOLD

    def round_up_int(self, num):
        return int(num + 0.5)

    def process_scl_file(self, scl_file):
        """Phase 0: SCL file processing"""
        num_processed_rows = 0
        row_height = self.DEFAULT_ROW_HEIGHT

        with open(scl_file, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            words = line.split()

            if not words or words[0] in ["#", "UCLA"]:
                i += 1
                continue

            if words[0] == "NumRows":
                num_rows = int(words[2])
                print(f"NumRows: {num_rows} are defined")
                i += 1
                continue

            if words[0] == "CoreRow":
                # Process CoreRow block
                i += 1
                line = lines[i].strip()
                words = line.split()

                # Coordinate
                if words[0] == "Coordinate":
                    row_y = int(words[2])
                else:
                    print("ERROR: CoreRow Processing: Coordinate keyword not found")
                    return False

                self.RowDB.append(row_y)

                # Height
                i += 1
                line = lines[i].strip()
                words = line.split()

                prev_row_height = row_height
                if words[0] == "Height":
                    row_height = int(words[2])
                else:
                    print("ERROR: CoreRow Processing: Height keyword not found")
                    return False

                if prev_row_height != row_height:
                    print(f"ERROR: Row Height mismatch: {prev_row_height} vs {row_height}")
                    return False

                # Skip Sitewidth, Sitespacing, Siteorient, Sitesymmetry
                for _ in range(4):
                    i += 1

                # SubrowOrigin
                i += 1
                line = lines[i].strip()
                words = line.split()

                if words[0] == "SubrowOrigin":
                    row_x = int(words[2])
                    row_num_sites = int(words[5])
                    self.RowDBstartX.append(row_x)
                    self.RowDBendX.append(row_x + row_num_sites)
                else:
                    print("ERROR: CoreRow Processing: SubrowOrigin keyword not found")
                    return False

                # Update window boundaries
                if self.WINDOW_LX > row_x:
                    self.WINDOW_LX = row_x
                if self.WINDOW_HX < row_x + row_num_sites:
                    self.WINDOW_HX = row_x + row_num_sites
                if self.WINDOW_LY > row_y:
                    self.WINDOW_LY = row_y
                if self.WINDOW_HY < row_y + row_height:
                    self.WINDOW_HY = row_y + row_height

                num_processed_rows += 1
                i += 1  # Skip End line

            i += 1

        print(f"Phase 0: Total {num_processed_rows} rows are processed.")
        print(
            f"         ImageWindow=({self.WINDOW_LX} {self.WINDOW_LY} {self.WINDOW_HX} {self.WINDOW_HY}) w/ row_height={row_height}")
        return True

    def process_node_file(self, nod_file):
        """Phase 1: Node file processing"""
        num_obj = 0
        num_terminal = 0

        with open(nod_file, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("UCLA"):
                continue

            words = line.split()
            if words[0] == "NumNodes":
                num_obj_from_file = int(words[2])
                # Next line should be NumTerminals
                continue
            if words[0] == "NumTerminals":
                num_term_from_file = int(words[2])
                print(f"NumNodes: {num_obj_from_file} NumTerminals: {num_term_from_file}")
                continue

            name = words[0]
            dx = int(words[1])
            dy = int(words[2])

            if len(words) > 3 and words[3] == "terminal":
                move_type = "terminal"
                num_terminal += 1
            else:
                move_type = "movable"

            self.ObjectDB[name] = [dx, dy, 0, 0, move_type]
            num_obj += 1

        print(f"Phase 1: Node file processing is done. Total {num_obj} objects (terminal {num_terminal})")
        return True

    def process_solution_file(self, sol_file):
        """Phase 2: Solution PL file processing"""
        num_obj = 0
        num_large_macro = 0

        with open(sol_file, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("UCLA"):
                continue

            words = line.split()
            name = words[0]
            locx = int(float(words[1]))
            locy = int(float(words[2]))

            if name not in self.ObjectDB:
                print(f"ERROR: Undefined object {name} appear in PL file.")
                return False

            self.ObjectDB[name][self.LOCXINDEX] = locx
            self.ObjectDB[name][self.LOCYINDEX] = locy
            num_obj += 1

            obj_dx = self.ObjectDB[name][self.DXINDEX]
            obj_dy = self.ObjectDB[name][self.DYINDEX]

            # Check for large internal macros
            if (self.is_large_macro(obj_dx, obj_dy) and
                    (locx >= self.WINDOW_LX) and (locy >= self.WINDOW_LY) and
                    (locx + obj_dx <= self.WINDOW_HX) and (locy + obj_dy <= self.WINDOW_HY)):
                num_large_macro += 1

        print(f"Phase 2: Solution PL file processing is done.")
        print(f"         Total {num_obj} objects. {num_large_macro} Large macros")
        return True

    def process_net_file(self, net_file):
        """Phase 3: NET file processing"""
        num_net = 0
        num_pin = 0
        index_net = 0
        total_wl = 0
        max_degree = 0
        num_fanout_clipped = 0
        num_less_than_two_pin_net = 0

        minx, miny, maxx, maxy = 100000000, 100000000, -1, -1

        with open(net_file, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#") or line.startswith("UCLA"):
                i += 1
                continue

            words = line.split()
            if words[0] == "NumNets":
                num_net_from_file = int(words[2])
                i += 1
                continue
            if words[0] == "NumPins":
                num_pin_from_file = int(words[2])
                print(f"NumNets: {num_net_from_file} NumPins: {num_pin_from_file}")
                i += 1
                continue
            if words[0] != "NetDegree":
                print(f"Error: Expected Keyword NetDegree does not show up. Instead {words[0]}")
                return False

            this_num_pin = int(words[2])
            this_net_name = words[3]

            if this_num_pin < 2:
                num_less_than_two_pin_net += 1

            tmpPinArray = []
            this_net_wl = 0
            this_net_lx, this_net_ly = 100000000, 100000000
            this_net_hx, this_net_hy = -1, -1

            for j in range(this_num_pin):
                i += 1
                line = lines[i].strip()
                words = line.split()

                obj_name = words[0]
                in_out = words[1]
                x_offset = int(float(words[3]))
                y_offset = int(float(words[4]))

                if obj_name not in self.ObjectDB:
                    print(f"ERROR: Object {obj_name} is NOT defined in ObjectDB.")
                    return False

                obj_lx = self.ObjectDB[obj_name][self.LOCXINDEX]
                obj_ly = self.ObjectDB[obj_name][self.LOCYINDEX]
                obj_dx = self.ObjectDB[obj_name][self.DXINDEX]
                obj_dy = self.ObjectDB[obj_name][self.DYINDEX]

                obj_cx = obj_lx + (obj_dx / 2)
                obj_cy = obj_ly + (obj_dy / 2)

                obj_x = obj_cx + x_offset
                obj_y = obj_cy + y_offset

                # Update global pin bounding box
                minx, miny = min(minx, obj_x), min(miny, obj_y)
                maxx, maxy = max(maxx, obj_x), max(maxy, obj_y)

                # Update net bounding box
                this_net_lx = min(this_net_lx, obj_x)
                this_net_ly = min(this_net_ly, obj_y)
                this_net_hx = max(this_net_hx, obj_x)
                this_net_hy = max(this_net_hy, obj_y)

                num_pin += 1
                tmpPinRecord = [obj_x, obj_y, self.DEFAULT_PIN_METAL_LAYER,
                                obj_lx, obj_ly, obj_dx, obj_dy, x_offset, y_offset]
                tmpPinArray.append(tmpPinRecord)

            # Store net data
            self.NetDB[this_net_name] = [index_net, this_num_pin]
            index_net += 1

            if this_num_pin > max_degree:
                max_degree = this_num_pin

            if this_num_pin > self.FANOUT_CLIP_THRESHOLD:
                num_fanout_clipped += 1

            self.NetPinDB[this_net_name] = tmpPinArray
            this_net_wl = ((this_net_hx - this_net_lx) + (this_net_hy - this_net_ly))

            if this_net_wl < 0:
                print(f"ERROR: Net {this_net_name} HPWL={this_net_wl} (negative wl)")
                return False

            total_wl += this_net_wl
            num_net += 1
            i += 1

        fanout_clipped_percent = (num_fanout_clipped / num_net) * 100 if num_net > 0 else 0

        print("Phase 3: Net file processing is done.")
        print(f"         Total {num_net} nets {num_pin} pins. Max degree: {max_degree} "
              f"FanoutClipped: {num_fanout_clipped} ({fanout_clipped_percent:.2f}%)")
        print(f"         Total HPWL: {total_wl} Less-than-two-pin-net: {num_less_than_two_pin_net}")

        # Return the pin bounding box
        return (minx, miny, maxx, maxy)

    def generate_benchmark(self, output_file, tile_size, adjustment_factor, safe_guard, mode, pin_bounds):
        """Phase 4: Generate routing benchmark"""

        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"Created output directory: {output_dir}")

        tile_width = tile_height = tile_size
        adjustment_factor /= 100.0
        safe_guard /= 100.0

        print(f"Phase 4: Generating a benchmark")

        # CORRECTED: Calculate routing area by taking the union of the SCL window and pin boundaries
        minx = min(self.WINDOW_LX, pin_bounds[0])
        miny = min(self.WINDOW_LY, pin_bounds[1])
        maxx = max(self.WINDOW_HX, pin_bounds[2])
        maxy = max(self.WINDOW_HY, pin_bounds[3])

        # Adjust boundaries for tile centers
        minx -= int(tile_width / 2.0)
        maxx += int(tile_width / 2.0)
        miny -= int(tile_height / 2.0)
        maxy += int(tile_height / 2.0)
        minx, miny = max(minx, 0), max(miny, 0)

        # Calculate grid dimensions
        image_dx = maxx - minx
        image_dy = maxy - miny
        xgrid = self.round_up_int(image_dx / tile_width)
        ygrid = self.round_up_int(image_dy / tile_height)

        # CORRECTED: Re-implement full capacity calculation for all modes
        m1_capacity = int(tile_height * 0.2 * safe_guard)
        if self.is_odd(m1_capacity): m1_capacity += 1
        m2_capacity = int(tile_width * 0.2 * safe_guard)
        if self.is_odd(m2_capacity): m2_capacity += 1

        base_hori_capacity = int(tile_height * safe_guard)
        if self.is_odd(base_hori_capacity): base_hori_capacity += 1

        base_vert_capacity = int(tile_width * safe_guard)
        if self.is_odd(base_vert_capacity): base_vert_capacity += 1

        with open(output_file, 'w') as f:
            # --- Header Section ---
            if mode == 3:
                numlayer = 6
                f.write(f"grid\t{xgrid}\t{ygrid}\t{numlayer}\n")
                f.write(f"vertical capacity\t0\t{m2_capacity}\t0\t{base_vert_capacity}\t0\t{base_vert_capacity}\n")
                f.write(f"horizontal capacity\t{m1_capacity}\t0\t{base_hori_capacity}\t0\t{base_hori_capacity}\t0\n")
                f.write("minimum width\t" + "\t".join(['1'] * numlayer) + "\n")
                f.write("minimum spacing\t" + "\t".join(['1'] * numlayer) + "\n")
                f.write("via spacing\t" + "\t".join(['1'] * numlayer) + "\n")
            else:  # mode == 2
                numlayer = 2
                d2_hori_base_capacity = m1_capacity + base_hori_capacity + base_hori_capacity
                if self.is_odd(d2_hori_base_capacity): d2_hori_base_capacity += 1
                d2_vert_base_capacity = m2_capacity + base_vert_capacity + base_vert_capacity
                if self.is_odd(d2_vert_base_capacity): d2_vert_base_capacity += 1

                f.write(f"grid\t{xgrid}\t{ygrid}\t{numlayer}\n")
                f.write(f"vertical capacity\t0\t{d2_vert_base_capacity}\n")
                f.write(f"horizontal capacity\t{d2_hori_base_capacity}\t0\n")
                f.write("minimum width\t1\t1\n")
                f.write("minimum spacing\t1\t1\n")
                f.write("via spacing\t1\t1\n")

            f.write(f"{int(minx)}\t{int(miny)}\t{tile_width}\t{tile_height}\n\n")

            # --- Nets Section ---
            updated_num_net = len([net for net in self.NetDB.values() if net[1] >= 2])
            f.write(f"num net\t{updated_num_net}\n")

            for net_name in sorted(self.NetPinDB.keys()):
                net_data = self.NetDB[net_name]
                net_id, num_pin = net_data

                if num_pin < 2:
                    continue

                tmpPinArray = self.NetPinDB[net_name]
                f.write(f"{net_name}\t{net_id}\t{num_pin}\t{self.DEFAULT_WIRE_MINIMUM_WIDTH}\n")

                for pin in tmpPinArray:
                    x, y, l = pin[0], pin[1], pin[2]
                    x = self.round_up_int(x)
                    y = self.round_up_int(y)
                    f.write(f"{x}\t{y}\t{l}\n")

            # --- Capacity Adjustments Section ---
            for name, obj_data in self.ObjectDB.items():
                obj_lx, obj_ly = obj_data[self.LOCXINDEX], obj_data[self.LOCYINDEX]
                obj_dx, obj_dy = obj_data[self.DXINDEX], obj_data[self.DYINDEX]

                if (self.is_large_macro(obj_dx, obj_dy) and
                        obj_lx >= self.WINDOW_LX and obj_ly >= self.WINDOW_LY and
                        obj_lx + obj_dx <= self.WINDOW_HX and obj_ly + obj_dy <= self.WINDOW_HY):

                    obj_hx, obj_hy = obj_lx + obj_dx, obj_ly + obj_dy

                    x_l_idx = int((obj_lx - minx) / tile_width)
                    x_h_idx = int((obj_hx - minx) / tile_width)
                    y_l_idx = int((obj_ly - miny) / tile_height)
                    y_h_idx = int((obj_hy - miny) / tile_height)

                    # Horizontal edges (R)
                    for iy in range(y_l_idx, y_h_idx + 1):
                        for ix in range(x_l_idx, x_h_idx):
                            key = f"{ix}:{iy}:R"
                            self.CapAdjustmentDB[key] = self.CapAdjustmentDB.get(key, 0) + 1

                    # Vertical edges (U)
                    for ix in range(x_l_idx, x_h_idx + 1):
                        for iy in range(y_l_idx, y_h_idx):
                            key = f"{ix}:{iy}:U"
                            self.CapAdjustmentDB[key] = self.CapAdjustmentDB.get(key, 0) + 1

            f.write(f"\n{len(self.CapAdjustmentDB)}\n")

            for key_string, val in self.CapAdjustmentDB.items():
                parts = key_string.split(':')
                row, col, direction = int(parts[0]), int(parts[1]), parts[2]

                if direction == "R":
                    newval = int(base_hori_capacity * (1.0 - val * adjustment_factor))
                    adjusted_value = max(0, newval)
                    i = row + 1

                    if mode == 3:
                        if self.is_odd(adjusted_value): adjusted_value += 1
                        f.write(f"{row}\t{col}\t3\t{i}\t{col}\t3\t{adjusted_value}\n")
                    else:  # mode == 2
                        # CORRECTED: Reconstruct the total adjusted capacity for mode 2
                        total_adjusted_value = m1_capacity + adjusted_value + base_hori_capacity
                        if self.is_odd(total_adjusted_value): total_adjusted_value += 1
                        f.write(f"{row}\t{col}\t1\t{i}\t{col}\t1\t{total_adjusted_value}\n")

                elif direction == "U":
                    newval = int(base_vert_capacity * (1.0 - val * adjustment_factor))
                    adjusted_value = max(0, newval)
                    i = col + 1

                    if mode == 3:
                        if self.is_odd(adjusted_value): adjusted_value += 1
                        f.write(f"{row}\t{col}\t4\t{row}\t{i}\t4\t{adjusted_value}\n")
                    else:  # mode == 2
                        # CORRECTED: Reconstruct the total adjusted capacity for mode 2
                        total_adjusted_value = m2_capacity + adjusted_value + base_vert_capacity
                        if self.is_odd(total_adjusted_value): total_adjusted_value += 1
                        f.write(f"{row}\t{col}\t2\t{row}\t{i}\t2\t{total_adjusted_value}\n")

        print(f"Benchmark generated: {output_file}")
        return True


# --- Main execution block for Kaggle ---
if __name__ == "__main__":
    import logging

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    generator = RoutingBenchmarkGenerator()

    # Define file paths and parameters
    nodes_file = r"/DREAMPlace\install\benchmarks\ispd2005\adaptec1\adaptec1.nodes"
    solution_file = r"/DREAMPlace\install\results\adaptec1\adaptec1.gp.pl"
    net_file = r"/DREAMPlace\install\benchmarks\ispd2005\adaptec1\/adaptec1.nets"
    scl_file = r"/DREAMPlace\install\benchmarks\ispd2005\adaptec1\adaptec1.scl"
    output_file = r"test_result\adaptec1_routing_input.gr"

    tile_size = 35
    adjustment_factor = 50
    safe_guard_factor = 90
    mode = 2

    # Execute pipeline
    exit_code = 0
    try:
        logger.info("Starting benchmark generation pipeline...")

        # Phase 0: SCL file processing
        logger.info(f"Phase 0: Processing SCL file: {scl_file}")
        if not generator.process_scl_file(scl_file):
            logger.error("Phase 0 FAILED: SCL file processing encountered errors")
            exit_code = 1
            sys.exit(exit_code)

        # Phase 1: Node file processing
        logger.info(f"Phase 1: Processing nodes file: {nodes_file}")
        if not generator.process_node_file(nodes_file):
            logger.error("Phase 1 FAILED: Nodes file processing encountered errors")
            exit_code = 2
            sys.exit(exit_code)

        # Phase 2: Solution file processing
        logger.info(f"Phase 2: Processing solution file: {solution_file}")
        if not generator.process_solution_file(solution_file):
            logger.error("Phase 2 FAILED: Solution file processing encountered errors")
            exit_code = 3
            sys.exit(exit_code)

        # Phase 3: Net file processing
        logger.info(f"Phase 3: Processing net file: {net_file}")
        pin_bounds = generator.process_net_file(net_file)
        if not pin_bounds:
            logger.error("Phase 3 FAILED: Net file processing encountered errors")
            exit_code = 4
            sys.exit(exit_code)

        # Phase 4: Benchmark generation
        logger.info(f"Phase 4: Generating routing benchmark with parameters:")
        logger.info(f"  - Tile size: {tile_size}")
        logger.info(f"  - Adjustment factor: {adjustment_factor}%")
        logger.info(f"  - Safe guard factor: {safe_guard_factor}%")
        logger.info(f"  - Mode: {mode}")
        logger.info(f"  - Output file: {output_file}")

        if not generator.generate_benchmark(output_file, tile_size, adjustment_factor, safe_guard_factor, mode, pin_bounds):
            logger.error("Phase 4 FAILED: Benchmark generation encountered errors")
            exit_code = 5
            sys.exit(exit_code)

        logger.info("="*60)
        logger.info("Benchmark generation completed successfully!")
        logger.info(f"Output written to: {output_file}")
        logger.info("="*60)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        logger.error("Please check that all input files exist and paths are correct")
        exit_code = 10
        sys.exit(exit_code)

    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        logger.error("Please check file/directory permissions")
        exit_code = 11
        sys.exit(exit_code)

    except ValueError as e:
        logger.error(f"Value error in processing: {e}")
        logger.error("Please check input file formats and data validity")
        exit_code = 12
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Unexpected error occurred: {type(e).__name__}")
        logger.error(f"Error details: {e}")
        logger.exception("Full traceback:")
        exit_code = 99
        sys.exit(exit_code)

    sys.exit(exit_code)
