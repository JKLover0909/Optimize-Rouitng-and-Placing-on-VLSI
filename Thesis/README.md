docker run --gpus 1 -it -v $(pwd):/DREAMPlace limbo018/dreamplace:cuda bash

python dreamplace/Placer.py test/ispd2005.adaptec1.json --plot_flag 1

# lần đầu
docker run --gpus all -it --name dreamplace_dev -v "$(pwd)":/DREAMPlace limbo018/dreamplace:cuda bash
# cài pip, sau đó thoát
# lần sau vào lại container đã cài sẵn
docker start -ai dreamplace_dev

# Macro only
python makePL_macro.py adaptec1 1000

# Standard cell only
python makePL_stdcell.py adaptec1 1000

# Fixed only
python makePL_fixed.py adaptec1

# Movable only
python makePL_movable.py adaptec1

# Chạy adaptec1
./run_dreamplace.sh adaptec1

# Chạy bigblue1
./run_dreamplace.sh bigblue1

streamlit run dreamplace_gui.py

python3 dreamplace_console.py