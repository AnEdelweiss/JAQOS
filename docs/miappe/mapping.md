---
title: Mapping variables sheet
parent: Filling the MIAPPE
nav_order: 8
---

# mapping_table_variables sheet :

This sheet is an addition to the original MIAPPE and can be deleted if you want to share the MIAPPE file.
It contains two columns :

- **column_in_data_table** : This column corresponds to the exact name of the columns in your tabular data file. **The names must exactly match**.
- **opensilex_variable_name** : This column corresponds to the name (or shortname) of the equivalent variable **on the PHIS instance**, thus, you have to manually create the variables if they do not already exist on your instance, then reference them here. The program will automatically pick the right variables for the right datafile, so you can safely copy-paste your 'mapping_table_variables' sheet onto different experiments, even if the variable is not used in the present experiment.

[example of a correctly filled sheet]