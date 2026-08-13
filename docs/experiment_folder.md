---
title: Experiment folder structure
layout: home
nav_order: 3
---

# The experiment structure.

Each experiment should have a dedicated folder, the filled miappe template for the experiment, the tabular data, the datafiles you would like to upload should all be inside this folder like so :


```bash
exp_database/
│
├── experiment_1/
│   ├── tabular_data_file_RGB1.xlsx
│	├──	tabular_data_file_archives.xlsx
│   ├── Miappe_template.xlsx
│   ├── 00-RoundProtocol/ (optional)
│   │   └── Round_protocol_files.txt 
│   ├── output/
│   │   └── miappe_template_filled.xlsx
│   ├── Archives_folder/ (optional)
│   │   └── archive1.tar
│   │   └── archive2.tar
│       └── archive....tar
│   └── Image_folder/ (optional)
│       └── image1.png
│       └── image2.png
│       └── image...png
├── experiment_2/
├── experiment_3/
└── experiment_.../
```