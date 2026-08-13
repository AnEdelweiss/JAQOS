---
title: Formatting tabular data files
nav_order: 4
---

# The tabular data file.

{: .highlight-title }
>Nota bene
>
>*All column names are case sensitive.*

## Mandatory modifications:

There is only two mandatory columns for tabular data, the 'timestamp' column and the 'germplasm' column.

- the **timestamp** column should contain the timestamp of when the data was collected following the standard : 'YYYY-MM-DD HH:MM:SS'.
  Valid exemples would be : 2025-01-12 12:10:56...
- the **germplasm** column should contain the germplasm's name.
  Valid exemples would be : ...

## Optional modifications:

However, **if you would like to link data to datafiles** (images, archives) you also need to create a column named '**Datafile1_Filename**' stating **for each row** the exact name of the datafile. This will be the first set of datafiles. If there is a second set of datafiles, derived from the first one, you will need to create a second column named '**Datafile2_Filename**' stating **for each row** the exact name of the datafile.

- the **Datafile1_Filename** & **Datafile2_Filename** columns should contain the exact filename of the datafile with it's extension (.png,.jpeg, .tar, .png etc).
  Valid exemples would be : 121_9_2024-06-24_07-24-41_2024_ToAB_Stress_79_RGB2_FishEyeCorrected.png, Archive-12.tar, 163-38-24_KuKa_117-Cst-L-1.1-Area 02-RGB2-FishEyeMasked-Crop.png... etc.. (((toolbox ?)))

[example of a correctly filled tabular data file]