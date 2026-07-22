import os
import json
import time
from lxml import etree as ET
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from simple.ui import console
from simple.auth import connexion
from simple.__init__ import __version__
from simple.systeme_logs import logger
from simple.erreurs import SimpleBaseException,DataImportError
import datetime
import concurrent.futures
    
def get_round_protocol_info(wd_experience,document_data):
    #Get RoundProtocol Infos 
    plant_mask = {}
    cam_pos = {}
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
            except Exception:
                with open(key) as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
        # Get plant_mask Info for all rounds 
            plant_mask_rd = {}
            for child in root.iter(PID):
                for subchild in child.iter("PlantMask"):
                    plant_mask_rd = {elem.tag: elem.text for elem in subchild}
                    round_index = int(value["Round"])
                    plant_mask[round_index] = plant_mask_rd

            cam_pos_rd = {}
            for child in root.iter(PID):
                cam_pos_rd.update(child.attrib)
            for child in root.iter(PID):
                for subchild in child.iter("Offset"):
                    cam_pos_rd.update({subchild.tag: subchild.text})
                    round_index = int(value["Round"])
                    cam_pos[round_index] = cam_pos_rd
        logger.info("Plant_mask and Camera Position Info found !")
    else:
        logger.warning("00-RoundProtocol folder missing (of if not in use)")
        return cam_pos, plant_mask, False
    return cam_pos, plant_mask, True

def parse_excel_for_metadata(df_data, dict_paths, prov, file_type):
    metadata_dict = {}
    for row in track(list(df_data.to_dict('records')), total=len(df_data), description="[green]processing metadatas[/green]"):
        exp_id = row['Experiment ID']
        round_order = row['Round Order']
        tray_id = row['Plant ID']
        pid = row.get("PID",None)
        
        if file_type == "datafile1":
            filename = row.get("Datafile1_Filename")
        else:
            filename = row.get("Datafile2_Filename")
            
        if pd.isna(filename) or filename not in dict_paths:
            logger.error(f"warning : {filename} in 'data files' sheet of the  MIAPPE file is either empty or maybe there is a typo etc...")
            raise SimpleBaseException(f"warning : {filename} in 'data files' sheet of the  MIAPPE file is either empty or maybe there is a typo etc...")
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

def get_existing_datafiles(dat_api, prov_uri, exp_uri):
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

def check_for_datafiles(document_data, repertoire_photos):
        #Liste des datafiles
    ls_files_dict = {}
    for (root, dirs, files) in os.walk(repertoire_photos):
        for filename in files:
            ls_files_dict[filename] = os.path.join(root, filename)

    df_data = pd.read_excel(document_data)
    #traitement des datafiles1
    dict_datafile1 = {}
    missing_datafile1 = set()
    if 'Datafile1_Filename' in df_data.columns:
        set_ls_datafile1 = set(df_data['Datafile1_Filename'].dropna().unique())
        dict_datafile1 = {f: ls_files_dict[f] for f in set_ls_datafile1 if f in ls_files_dict}
        missing_datafile1 = set_ls_datafile1 - set(dict_datafile1.keys())
    else:
        logger.error("User tried to import datafiles without 'datafile1_Filename column")
        raise DataImportError("You are importing datafiles, you have to specify the name of the file for each row in a column named 'Datafile1_Filename'\n Leaving client.[/bold red]")
    #traitement des datafiles2
    has_datafile2 = 'Datafile2_Filename' in df_data.columns
    dict_datafile2 = {}
    missing_datafile2 = set()
    if has_datafile2:
        set_ls_datafile2 = set(df_data['Datafile2_Filename'].dropna().unique())
        dict_datafile2 = {f: ls_files_dict[f] for f in set_ls_datafile2 if f in ls_files_dict}
        missing_datafile2 = set_ls_datafile2 - set(dict_datafile2.keys())
    
    return dict_datafile1, missing_datafile1, dict_datafile2, missing_datafile2, has_datafile2, df_data

def execute_datafiles_upload(document_miappe,document_data, df_data, dict_datafile1, dict_datafile2, has_datafile2, prov_dict, datafile_provenance, sci_obj_uri, cam_pos, plant_mask, login, silex_API_Client,status_callback=None, progress_callback=None):
    
    connexion(login, silex_API_Client)
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    name_exp = dataframe['name'].dropna().iloc[0]
    exp_search = silex.ExperimentsApi(silex_API_Client).search_experiments(name=name_exp)["result"]
    exp_uri = exp_search[0].uri
    #GETTING PID and angle
    if 'PID' in df_data.columns:
        pid = df_data['PID'].unique()[0]
        if status_callback:
            status_callback(f'[bold cyan][✓] PID found:[/bold cyan] {pid}')
        logger.info(f'[bold cyan][✓] PID found:[/bold cyan] {pid}')
    else :
        pid = None
    if 'Angle' not in df_data.columns:
        df_data["Angle"] = None
        if status_callback:
            status_callback("No angle data was found in the tabular data. It is not a problem, if it is intentional.")
        logger.info("No angle data was found in the tabular data. It is not a problem, if it is intentional.")

    dat_api = silex.DataApi(silex_API_Client)
    datafile_name = os.path.basename(document_data)
    provenance_datafile1 = None
    provenance_datafile2 = None
    rdf_type_1 = None
    rdf_type_2 = None
    for suffix, config in datafile_provenance.items():
        if datafile_name == suffix:
            val1 = config.get("prov_datafiles1")
            rdf1 = config.get("rdf_type_datafile1")
            val2 = config.get("prov_datafiles2")
            rdf2 = config.get("rdf_type_datafile2")
            provenance_datafile1 = prov_dict.get(val1) if not pd.isna(val1) else None
            rdf_type_1 = rdf1 if not pd.isna(rdf1) else None
            provenance_datafile2 = prov_dict.get(val2) if not pd.isna(val2) else None
            rdf_type_2 = rdf2 if not pd.isna(rdf2) else None
            break
    if status_callback:
        status_callback(f"[green][✓] Provenance for datafile1 found : {provenance_datafile1}[/green]")
    logger.info(f"[green][✓] Provenance for datafile1 found : {provenance_datafile1}[/green]")
    if provenance_datafile2 is not None:
        if status_callback:
            status_callback(f"[green][✓] Provenance for datafile2 found : {provenance_datafile2}[/green]")
        logger.info(f"[green][✓] Provenance for datafile2 found : {provenance_datafile2}[/green]")

    # IMPORT DATAFILE 1
    corr_data = parse_excel_for_metadata(df_data, dict_datafile1, provenance_datafile1, "datafile1")
    if status_callback:
        status_callback("[green][✓] datafile1 data parsing OK [/green]")
    logger.info("[green][✓] datafile1 data parsing OK [/green]")
    existing_datafile1_keys = get_existing_datafiles(dat_api, provenance_datafile1, exp_uri)
    if status_callback:
        status_callback("[green][✓] Search for existing datafiles1 OK [/green]")
    logger.info("[green][✓] Search for existing datafiles1 OK [/green]")
    
    corr_to_upload = [
        img for img in corr_data.values() 
        if (sci_obj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile1_keys
    ]

    # ####TEST :
    toutes_datafile1_triees = sorted(corr_data.values(), key=lambda x: x["Path"])
    
    # On isole les 5 premières pour le test
    datafile1_test_subset = toutes_datafile1_triees[30:35]

    corr_to_upload = [
        img for img in datafile1_test_subset 
        if (sci_obj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile1_keys
    ]
    # ###TEST
    if status_callback:
        status_callback(f"[bold green]{len(corr_data) - len(corr_to_upload)}[cyan] Datafiles1 exists on [bold green]{len(corr_data)}[/bold green] total [/cyan]")
    logger.info(f"[bold green]{len(corr_data) - len(corr_to_upload)}[cyan] Datafiles1 exists on [bold green]{len(corr_data)}[/bold green] total [/cyan]")

    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
    
    def process_datafile1(img):
        path_ou_post = 0
        round_order = int(img.get("Round Order"))
        cam_pos_round = cam_pos.get(round_order, {}) 
        settings_dict = {}
        if img.get("Angle") is not None:
            settings_dict["Camera Angle"] = img.get("Angle")
        if cam_pos_round.get("height") is not None:
            settings_dict["Camera Height"] = cam_pos_round.get("height")
        if cam_pos_round.get("Offset") is not None:
            settings_dict["Offset"] = cam_pos_round.get("Offset")
            
        desc = {
            "rdf_type": f"vocabulary:{rdf_type_1}",
            "date": img["Date"],
            "target": sci_obj_uri[img["Plant ID"]],
            "metadata": {"Round Order": round_order, "Imported with": f"SIMPLE {__version__}"},
            "provenance": {
                "uri": img["Prov"],
                "settings": settings_dict,
                "experiments": [exp_uri]
            }
        }
        if path_ou_post == 1:
            dat_api.post_data_file_paths(body=[
                silex.DataFilePathCreationDTO(
                    rdf_type= f"vocabulary:{rdf_type_1}",
                    _date= img["Date"],
                    target=sci_obj_uri[img["Plant ID"]],
                    metadata={
                        "Round Order": round_order,
                        "Imported with": f"SIMPLE {__version__}"
                        },
                    provenance={
                        "uri": img["Prov"],
                        "settings": settings_dict,
                        "experiments": [exp_uri]
                        },
                    relative_path="" + os.path.basename(img["Path"]))])
        else:
            dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

    nom_tache_datafile1="[bold blue]Uploading datafiles 1...[/bold blue]"
    if progress_callback and len(corr_to_upload)>0:
        progress_callback(nom_tache_datafile1,total=len(corr_to_upload))

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_datafile1, img) for img in corr_to_upload]
        for future in concurrent.futures.as_completed(futures):
            if datetime.datetime.now() > timelimit:
                connexion(login, silex_API_Client)
                timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
            
            try:
                future.result()
            except Exception as e :
                logger.error(f"failed to upload image :{e} ")
                if status_callback:
                    status_callback("[bold yellow] /!\ A datafile failed to upload, please check the logs for informations, continuing...[/bold yellow]")
            if progress_callback:
                progress_callback(nom_tache_datafile1,avance=1)

    if status_callback:
        status_callback("[green][✓] Datafile1 upload complete! [/green]")
    logger.info("[green][✓] Datafile1 upload complete! [/green]")

    # IMPORT DATAFILE 2 (OPTIONNEL)
    if has_datafile2 and provenance_datafile2:
        with console.status("Waiting for Datafiles 1..."):
            time.sleep(2)
        datafile1_uri_map = {
            (elts.target, elts._date): elts.uri
            for elts in dat_api.get_data_file_descriptions_by_search(
                provenances=[provenance_datafile1], experiments=[exp_uri], page_size=100000
            )["result"]
        }

        mask_data = parse_excel_for_metadata(df_data, dict_datafile2, provenance_datafile2, "datafile2")
        if status_callback:
            status_callback("[green][✓] datafile2 data parsing OK [/green]")
        logger.info("[green][✓] datafile2 data parsing OK [/green]")

        for img in mask_data.values():
            target = sci_obj_uri[img["Plant ID"]]
            date = img["Date"].replace('+', '.000+')
            uri_trouve = datafile1_uri_map.get((target,date))
            img["Prov_Used"] = uri_trouve

        existing_datafile2_keys = get_existing_datafiles(dat_api, provenance_datafile2, exp_uri)
        if status_callback:
            status_callback("[green][✓] Search for existing datafiles2 OK [/green]")
        logger.info("[green][✓] Search for existing datafiles2 OK [/green]")

        mask_to_upload = [
            img for img in mask_data.values()
            if (sci_obj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile2_keys
        ]

        # # TEST TEST TEST
        toutes_datafile2_triees = sorted(mask_data.values(), key=lambda x: x["Path"])
        
        datafile2_test_subset = toutes_datafile2_triees[30:35]

        mask_to_upload = [
            img for img in datafile2_test_subset 
            if (sci_obj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_datafile2_keys
        ]
        # # # TEST TEST TEST

        status_callback(f"[bold green]{len(mask_data) - len(mask_to_upload)} [cyan]Datafiles2 exists on[/cyan] {len(mask_data)}[cyan] total[/bold green]")
        logger.info(f"[bold green]{len(mask_data) - len(mask_to_upload)} [cyan]Datafiles2 exists on[/cyan] {len(mask_data)}[cyan] total[/bold green]")
        def process_datafile2(img):
            round_order = int(img.get("Round Order"))
            settings = {"Camera Angle": img.get("Angle")}
            if round_order in plant_mask:
                settings.update(plant_mask[round_order])

            desc = {
                "rdf_type": f"vocabulary:{rdf_type_2}",
                "date": img["Date"],
                "target": sci_obj_uri[img["Plant ID"]],
                "metadata": {"Round Order": round_order, "Imported with": f"SIMPLE {__version__}"},
                "provenance": {
                    "uri": img["Prov"],
                    "prov_used": [{"uri": img["Prov_Used"], "rdf_type": f"vocabulary:{rdf_type_1}"}] if img.get("Prov_Used") else [],
                    "settings": settings,
                    "experiments": [exp_uri]
                }
            }
            dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

        nom_tache_datafile2="[bold blue]Uploading datafiles 2...[/bold blue]"

        if progress_callback and len(mask_to_upload)>0:
            progress_callback(nom_tache_datafile2,total=len(mask_to_upload))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_datafile2, img) for img in mask_to_upload]
            for future in concurrent.futures.as_completed(futures):
                if datetime.datetime.now() > timelimit:
                    connexion(login, silex_API_Client)
                    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
                try:
                    future.result()
                except Exception as e :
                    logger.error(f"failed to upload image :{e} ")
                    if status_callback:
                        status_callback("[bold yellow] /!\ A datafile failed to upload, please check the logs for informations, continuing...[/bold yellow]")
                    
                    if progress_callback:
                        progress_callback(nom_tache_datafile2,avance=1)
            
        if status_callback:
            status_callback("[green][✓] Datafile2 upload complete! [/green]")
        logger.info("[green][✓] Datafile2 upload complete! [/green]")
    return 1
