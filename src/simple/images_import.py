import sys
import os
import json
from lxml import etree as ET
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from rich.table import Table
from simple.ui import console
from simple.auth import connexion
from simple.data_import import create_sci_obj, get_provenances
from simple.__init__ import __version__
import datetime
from rich.prompt import Prompt
import concurrent.futures

def create_images(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client):

    prov_dict,datafile_provenance=get_provenances(document_data,document_miappe,silex_API_Client)
    ScObj_uri=create_sci_obj(document_data,document_miappe,silex_API_Client)
    import_images(document_miappe,document_data,wd_experience,prov_dict,datafile_provenance,ScObj_uri,repertoire_photos,login,silex_API_Client)
    return prov_dict
    
def get_round_protocol_info(wd_experience,document_data):
    #Get RoundProtocol Infos 
    PlantMask = {}
    CamPos = {}
    Round_folder = os.path.join(wd_experience, '00-RoundProtocol')
    if os.path.isdir(Round_folder):
        Round_files = []
        for (root, dirs, files) in os.walk(Round_folder):
            for name in files:
                Round_files.append(os.path.join(root, name))

        Exp_Rd_Dict = {}
        for wd_round in Round_files:
            filename = os.path.basename(wd_round).replace(".txt", "")
            Exp_Rd_ls = filename.split("-")
            Exp_Rd_Dict.update({wd_round: {"Experiment": Exp_Rd_ls[1], "Round": (Exp_Rd_ls[2][0:3]).replace("_","")}})
        # Create Dictionary for all parameters 
        df_data = pd.read_excel(document_data)
        PID = df_data['PID'].unique()[0]
        # Transform RoundProtocol to xml 
        for key, value in Exp_Rd_Dict.items():
            try:
                with open(key, encoding='utf-16') as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
            except Exception as e:
                with open(key) as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
        # Get PlantMask Info for all rounds 
            PlantMask_rd = {}
            for child in root.iter(PID):
                for subchild in child.iter("PlantMask"):
                    PlantMask_rd = {elem.tag: elem.text for elem in subchild}
                    round_index = int(value["Round"])
                    PlantMask[round_index] = PlantMask_rd

            CamPos_rd = {}
            for child in root.iter(PID):
                CamPos_rd.update(child.attrib)
            for child in root.iter(PID):
                for subchild in child.iter("Offset"):
                    CamPos_rd.update({subchild.tag: subchild.text})
                    round_index = int(value["Round"])
                    CamPos[round_index] = CamPos_rd
        console.print("[bold green][✓] PlantMask and Camera Position Info found ![/bold green]")
    else:
        stop = Prompt.ask("[bold red][×] PlantMask and Camera Position was not found, do you want to continue?\n(00-RoundProtocol missing) [/bold red]", choices=["y", "n"], default="y")
        if stop == "n":
            console.print("[bold red]OK, exiting client ![/bold red]")
            sys.exit()
    return CamPos,PlantMask

def parse_excel_for_metadata(df_data, dict_paths, prov, file_type):
    metadata_dict = {}
    for row in track(list(df_data.to_dict('records')), total=len(df_data), description="[green]processing metadatas[/green]"):
        exp_id = row['Experiment ID']
        round_order = row['Round Order']
        tray_id = row['Plant ID']
        pid = row['PID']
        
        if file_type == "datafile1":
            filename = row.get("FEC_Filename")
        else:
            filename = row.get("FEM_Filename")
            
        if pd.isna(filename) or filename not in dict_paths:
            console.print(f"warning : {filename}")
            continue

        desired_format = "%Y-%m-%dT%H:%M:%S%z"
        row['Measuring Date'] = row['Measuring Date'].date()
        row['Measuring Time'] = row['Measuring Time'].tz_localize('UTC').tz_convert('Europe/Helsinki').strftime(desired_format)
        date = row['Measuring Time']

        metadata = {
            "Path": dict_paths[filename],
            "Experiment ID": exp_id,
            "Round Order": round_order,
            "Date": date,
            "Plant ID": tray_id,
            "PID": pid,
            "Prov": prov,
            "ImgType": filename.replace('-','_').split("_")[-1]
        }

        if 'Angle' in row:
            metadata["Angle"] = row['Angle']
        metadata_dict[filename] = metadata
        
    return metadata_dict

def get_existing_images(dat_api, prov_uri, exp_uri):
    if not prov_uri:
        return set()
    # On prends le set de tuples (target, date, angle, round_order) existants
    dat_src = dat_api.get_data_file_descriptions_by_search(
        provenances=[prov_uri], experiments=[exp_uri], page_size=100000
    )["result"]
    
    return {
        (elts.target, elts._date, elts.provenance.settings.get("Camera Angle"), elts.metadata.get('Round Order'))
        for elts in dat_src
    }

def import_images(document_miappe, document_data, wd_experience, prov_dict, datafile_provenance, ScObj_uri, repertoire_photos, login, silex_API_Client):
    connexion(login, silex_API_Client)
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    name_exp = dataframe['name'].dropna().iloc[0]
    exp_search = silex.ExperimentsApi(silex_API_Client).search_experiments(name=name_exp)["result"]
    exp_uri = exp_search[0].uri
    #GETTING PID   
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]
    console.print(f'[bold cyan][✓] PID found:[/bold cyan] {pid}')
    if 'Angle' not in df_data.columns:
        df_data["Angle"] = None
        console.print("[red][×] No angle data found in the tabular data. It is not a problem, if it is intentional.")
    
    #Liste des images
    ls_files_dict = {}
    for (root, dirs, files) in os.walk(repertoire_photos):
        for filename in files:
            ls_files_dict[filename] = os.path.join(root, filename)

    #traitement des datafiles1
    dict_datafile1 = {}
    missing_datafile1 = set()
    if 'FEC_Filename' in df_data.columns:
        set_ls_datafile1 = set(df_data['FEC_Filename'].dropna().unique())
        dict_datafile1 = {f: ls_files_dict[f] for f in set_ls_datafile1 if f in ls_files_dict}
        missing_datafile1 = set_ls_datafile1 - set(dict_datafile1.keys())
        if missing_datafile1:
            console.print(f"{len(missing_datafile1)} [red][×] images are missing from the datafile1 picture database..[/red]")
            if Prompt.ask("show the missing pictures?", choices=["y", "n"], default="y") == "y":
                console.print(missing_datafile1)
    else:
        console.print("[bold red][×] You are importing datafiles, you have to specify the name of the file for each row in a column named 'FEC_Filename'\n Leaving client.[/bold red]")
    #traitement des datafiles2
    has_datafile2 = 'FEM_Filename' in df_data.columns
    dict_datafile2 = {}
    missing_datafile2 = set()
    if has_datafile2:
        set_ls_datafile2 = set(df_data['FEM_Filename'].dropna().unique())
        dict_datafile2 = {f: ls_files_dict[f] for f in set_ls_datafile2 if f in ls_files_dict}
        missing_datafile2 = set_ls_datafile2 - set(dict_datafile2.keys())
        if missing_datafile2:
            console.print(f"{len(missing_datafile2)} [red][×] images are missing from the datafile2 picture database..[/red]")
            if Prompt.ask("show the missing pictures?", choices=["y", "n"], default="y") == "y":
                console.print(missing_datafile2)

    if len(missing_datafile1) + len(missing_datafile2) == 0:
        console.print("[green][✓] The image database matches the data, we can continue[/green]")
    else:
        if Prompt.ask("[red]Continue despite decrepancies ? The import may fail..[/red]", choices=["y", "n"], default="n") == "n":
            console.print("[bold red]OK, exiting client ![/bold red]")
            sys.exit()

    console.print(f'[bold cyan]There is :[/bold cyan] [bold green]{len(dict_datafile1)} [/bold green][bold cyan]items for datafile1.\nThere is :[/bold cyan] [bold green]{len(dict_datafile2)} [bold cyan]items for datafile2[/bold cyan]')    
    stop = Prompt.ask("[bold green]Do you want to continue to import images?[/bold green]", choices=["y", "n"], default="y")
    if stop == "n":
        console.print("[bold red]OK, exiting client ![/bold red]")
        sys.exit()

    CamPos, PlantMask = get_round_protocol_info(wd_experience, document_data)
    console.print("[green][✓][/green] [cyan] Round Protocol infos OK ![/cyan] ")
    dat_api = silex.DataApi(silex_API_Client)
    
    datafile_name = os.path.basename(document_data)
    provenance_image1 = None
    provenance_image2 = None
    for suffix, config in datafile_provenance.items():
        if datafile_name == suffix:
            val1 = config.get("prov_datafiles1")
            val2 = config.get("prov_datafiles2")
            provenance_image1 = prov_dict.get(val1) if not pd.isna(val1) else None
            provenance_image2 = prov_dict.get(val2) if not pd.isna(val2) else None
            break
    
    console.print(f"[green][✓] Provenance for datafile1 found : {provenance_image1}[/green]")
    if provenance_image2 is not None:
        console.print(f"[green][✓] Provenance for datafile2 found : {provenance_image2}[/green]")

    # IMPORT DATAFILE 1
    corr_data = parse_excel_for_metadata(df_data, dict_datafile1, provenance_image1, "datafile1")
    console.print("[green][✓] datafile1 data parsing OK [/green]")
    existing_datafile1_keys = get_existing_images(dat_api, provenance_image1, exp_uri)
    console.print("[green][✓] Search for existing datafiles1 OK [/green]")
    
    corr_to_upload = [
        img for img in corr_data.values() 
        if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile1_keys
    ]

    console.print(f"[bold green]{len(corr_data) - len(corr_to_upload)}[cyan] Datafiles1 exists on [bold green]{len(corr_data)}[/bold green] total [/cyan]")

    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
    
    def process_datafile1(img):
        round_order = int(img.get("Round Order"))
        cam_pos_round = CamPos.get(round_order, {}) 
        settings_dict = {}
        if img.get("Angle") is not None:
            settings_dict["Camera Angle"] = img.get("Angle")
        if cam_pos_round.get("height") is not None:
            settings_dict["Camera Height"] = cam_pos_round.get("height")
        if cam_pos_round.get("Offset") is not None:
            settings_dict["Offset"] = cam_pos_round.get("Offset")
            
        desc = {
            "rdf_type": "vocabulary:RGBImage",
            "date": img["Date"],
            "target": ScObj_uri[img["Plant ID"]],
            "metadata": {"Round Order": round_order, "Imported with": f"SIMPLE {__version__}"},
            "provenance": {
                "uri": img["Prov"],
                "settings": settings_dict,
                "experiments": [exp_uri]
            }
        }
        dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_datafile1, img) for img in corr_to_upload]
        for future in track(concurrent.futures.as_completed(futures), total=len(futures), description="[bold green]Uploading Datafile1[/bold green]"):
            if datetime.datetime.now() > timelimit:
                connexion(login, silex_API_Client)
                timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
            future.result()

    # IMPORT DATAFILE 2 (OPTIONNEL)
    if has_datafile2 and provenance_image2:
        datafile1_uri_map = {
            (elts.target, elts._date): elts.uri
            for elts in dat_api.get_data_file_descriptions_by_search(
                provenances=[provenance_image1], experiments=[exp_uri], page_size=100000
            )["result"]
        }

        mask_data = parse_excel_for_metadata(df_data, dict_datafile2, provenance_image2, "datafile2")
        console.print("[green][✓] datafile2 data parsing OK [/green]")

        for img in mask_data.values():
            target = ScObj_uri[img["Plant ID"]]
            date = img["Date"].replace('+', '.000+')
            img["Prov_Used"] = datafile1_uri_map.get((target, date))

        existing_datafile2_keys = get_existing_images(dat_api, provenance_image2, exp_uri)
        console.print("[green][✓] Search for existing datafiles2 OK [/green]")

        mask_to_upload = [
            img for img in mask_data.values()
            if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile2_keys
        ]

        console.print(f"[bold green]{len(mask_data) - len(mask_to_upload)} [cyan]Datafiles2 exists on[/cyan] {len(mask_data)}[cyan] total[/bold green]")

        def process_datafile2(img):
            round_order = int(img.get("Round Order"))
            settings = {"Camera Angle": img.get("Angle")}
            if round_order in PlantMask:
                settings.update(PlantMask[round_order])

            desc = {
                "rdf_type": "vocabulary:RGBImage",
                "date": img["Date"],
                "target": ScObj_uri[img["Plant ID"]],
                "metadata": {"Round Order": round_order, "Imported with": f"SIMPLE {__version__}"},
                "provenance": {
                    "uri": img["Prov"],
                    "prov_used": [{"uri": img["Prov_Used"], "rdf_type": "vocabulary:RGBImage"}] if img.get("Prov_Used") else [],
                    "settings": settings,
                    "experiments": [exp_uri]
                }
            }
            dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_datafile2, img) for img in mask_to_upload]
            for future in track(concurrent.futures.as_completed(futures), total=len(futures), description="[bold blue]Uploading Datafile2[/bold blue]"):
                if datetime.datetime.now() > timelimit:
                    connexion(login, silex_API_Client)
                    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
                future.result()

    console.print('[bold green][✓] Succeeded in importing images ![/bold green]')