<img src="simple_square.png" alt="icon" width="200" height="200">

### Simple Interface MIAPPE-Phis, Lightweight & Efficient

[WIP documentation](https://anedelweiss.github.io/SIMPLE/)



  V click here for a Quick Demo ! V

![Asciinema](simple.gif "Asciinema")

or here : [asciinema link](https://asciinema.org/a/wbQdA2NXiHwN86DZ)

Dummy experiment on Phis to show how the final experiment would look : [link to sandbox](https://opensilex.org/sandbox/app/experiment/details/opensilex-sandbox%3Aid%2Fexperiment%2Fdummy_experiment)


## Description.

In the context of my internship, I am working on SIMPLE, a Command Line Interface coded in python with a focus on ease of use, rapidity and flexibility. This tool will ( I hope ) help researchers upload MIAPPE compliant phenotyping data on OpenSilex instances without any efforts. Allowing them to keep germplasm banks up to date, to create experiments, create or add scientific objects to an experiment, add pictures, DATA and more.

## Before the first run :

As of now, the file structure should follow the example below  :

```
exp_database/
│
├── experiment_1/
│   ├── tabular_data_file_RGB1.xlsx
│	  ├──	tabular_data_file_archives.xlsx
│   ├── Miappe_template.xlsx
│   ├── 00-RoundProtocol/ (optional)
│   │   └── Round_protocol_files.txt 
│   ├── output/
│   │   └── miappe_template_filled.xlsx
│   ├── Archives/ (optional)
│   │   └── archive1.tar
│   │   └── archive2.tar
│   └── RGB1/ (optional)
│       └── image1.png
│       └── image2.png
├── experiment_2/
├── experiment_3/
└── experiment_.../
```

## Download

You can go to 'releases' section here : [Releases](https://github.com/AnEdelweiss/SIMPLE/releases)
and download the latest one for your distribution (Linux/Windows), then just double click it ! and follow the instructions ;)

## The input miappe file

as this is a work in progress, works with the current MIAPPE table provided in Miappe_Template.xlsx

You can change the order of the sheets, but you should NOT rename sheet names, this is what the script is using to read read data from.
Likewise, do NOT  rename the 2nd row  of each sheet nor delete it.

## The output miappe file

In the output folder, this is the final MIAPPE file that you shall upload on phis along with the experiment.
You should NOT rename this file NOR change the name of the sheets, this is what the script is using to read data from.

## The tabular data

as this is a work in progress,works with the tabular data provided in exp_database/test_SIMPLE/RGB1_Morpho_Manual.xlsx

## Instructions for using the code with an IDE :

This project requires Python 3.14.

- git clone https://github.com/AnEdelweiss/SIMPLE.git
- cd SIMPLE
- uv venv
- uv pip install -r pyproject.toml
- uv run simple

You can then use the provided dummy experiment in test_SIMPLE, you can also modify the content of the miappe_template to try and create different experiments, germplasms etc...
Everything should work !

## Project roadmap :

- Creating a 'troubleshooting/Q&A' section and a more thorough tutorial/doc :)
- Make a logo for the program :p
- Automation(?)
- ~~Change factor/factor level fetching and measuring date/measuring time from tabular data.~~
- Generalization : ~~changing the hardcoded provenances and PID~~, create the output document properly (and the output folder in the experiment directory etc...)
- ~~Updating the blank miappe available in the github~~
- ~~refactoring :-(~~
- ~~Using the rich library.~~
- ~~English translation.~~
- ~~Photo upploadng.~~
- ~~Make a 'help' feature in the CLI~~
- ~~Data upploading.~~
- ~~Reading the image names from the tabular data file and comparing them to those found locally. Thus limiting the parsing data from filename and using directly the tabular data.~~
- ~~Generalization : no more 'fec' and 'fem' when importing images, 'do you want to import 1 or 2 sets of datafiles (one obtained from the first one)' ability to import more than just images (tar files, fluorescence data...)~~
- ~~Logging everything into a log-dd-mm-yyyy.log to keep a written trace of what has been done during the session.~~
