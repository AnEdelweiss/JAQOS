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
from simple.data_import import create_sci_obj,create_provenances
import datetime
from rich.prompt import Prompt

def create_images(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client):

    TimeStamp=link_image_time(document_data)
    prov_dict=create_provenances(document_data,document_miappe,silex_API_Client)
    ScObj_uri=create_sci_obj(document_data,document_miappe,silex_API_Client)
    import_images(document_miappe,document_data,wd_experience,TimeStamp,prov_dict,ScObj_uri,repertoire_photos,login,silex_API_Client)
    return prov_dict
    
def get_round_protocol_info(wd_experience,document_data):
        ### Get RoundProtocol Infos 
    PlantMask = {}
    CamPos = {}
    Round_folder = os.path.join(wd_experience, '00-RoundProtocol')
    if os.path.isdir(Round_folder):
        Round_files = []
        for (root, dirs, files) in os.walk(Round_folder):
            for name in files:
                Round_files.append(os.path.join(root, name))

        ## Link RoundProtocol wd with Experiment and Round Numbers 
        Exp_Rd_Dict = {}
        for wd_round in Round_files:
            filename = os.path.basename(wd_round).replace(".txt", "")
            Exp_Rd_ls = filename.split("-")
            Exp_Rd_Dict.update({wd_round: {"Experiment": Exp_Rd_ls[1], "Round": (Exp_Rd_ls[2][0:3]).replace("_","")}})
        ## Create Dictionary for all parameters 
        df_data = pd.read_excel(document_data)
        PID = df_data['PID'].unique()[0]
        ## Transform RoundProtocol to xml 
        for key, value in Exp_Rd_Dict.items():
            try:
                with open(key,encoding='utf-16') as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
            except Exception as e:
                with open(key) as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
        ## Get PlantMask Info for all rounds 
            PlantMask_rd = {}
            for child in root.iter(PID):
                for subchild in child.iter("PlantMask"):
                    PlantMask_rd = {elem.tag: elem.text for elem in subchild}
                    round_index = int(value["Round"])
                    PlantMask[round_index] = PlantMask_rd

        # ## Get Camera Position Info for all rounds 
            CamPos_rd = {}
            for child in root.iter(PID):
                CamPos_rd.update(child.attrib)
            for child in root.iter(PID):
                for subchild in child.iter("Offset"):
                    CamPos_rd.update({subchild.tag: subchild.text})
                    round_index = int(value["Round"])
                    CamPos[round_index] = CamPos_rd
        # console.print(PlantMask)
        # console.print(CamPos)
        console.print("[bold green]PlantMask and Camera Position Info found ![/bold green]")
    else :
        stop=Prompt.ask("[bold red]PlantMask and Camera Position was not found, do you want to continue?\n(00-RoundProtocol missing) [/bold red]", choices=["y", "n"], default="y")
        if stop =="n":
            console.print("[bold red]OK, exiting client ![/bold red]")
            sys.exit()
    return CamPos,PlantMask

def link_image_time(document_data):
    
    df_data = pd.read_excel(document_data)
    desired_format = "%Y-%m-%dT%H:%M:%S%z"
    df_data['Measuring Date'] = df_data['Measuring Date'].dt.date
    df_data['Measuring Time'] = df_data['Measuring Time'].dt.tz_localize('UTC').dt.tz_convert('Europe/Helsinki').dt.strftime(desired_format)
    if 'Angle' in df_data.columns:
        df_data['Img Name'] = df_data.apply(lambda row: f"{row['Experiment ID']}-{row['Round Order']}-{row['Plant ID']}-{row['PID']}-{row['Angle']:03}", axis=1)
    else:
        df_data['Img Name'] = df_data.apply(lambda row: f"{row['Experiment ID']}-{row['Round Order']}-{row['Plant ID']}-{row['PID']}", axis=1)
    print(df_data['Img Name'])
    # Get Round Info in Dict 
    TimeStamp={}
    for index, row in df_data.iterrows():
        TimeStamp.update({row["Img Name"]: row['Measuring Time']})
    return TimeStamp

def parse_excel_for_metadata(df_data,dict,prov,fem_or_fec):
    metadata_dict={}
    for row in track(list(df_data.to_dict('records')),total=len(df_data), description="[green]processing metadatas[/green]"):
        exp_id = row['Experiment ID']
        round_order = row['Round Order']
        tray_id=row['Plant ID']
        pid=row['PID']
        if fem_or_fec == "fec":
            filename=row["FEC_Filename"]
        else :
            filename=row["FEM_Filename"]
        desired_format = "%Y-%m-%dT%H:%M:%S%z"
        row['Measuring Date'] = row['Measuring Date'].date()
        row['Measuring Time'] = row['Measuring Time'].tz_localize('UTC').tz_convert('Europe/Helsinki').strftime(desired_format)
        date = row['Measuring Time']

        metadata = {
            "Path": dict[filename],
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
        metadata_dict[filename]=metadata
        
    return metadata_dict

def get_existing_images(dat_api, prov_uri, exp_uri):
    # On prends le set de tuples (target, date, angle, round_order) existants
    dat_src = dat_api.get_data_file_descriptions_by_search(
        provenances=[prov_uri], experiments=[exp_uri], page_size=100000
    )["result"]
    
    return {
        (elts.target, elts._date, elts.provenance.settings.get("Camera Angle"), elts.metadata.get('Round Order'))
        for elts in dat_src
    }

def import_images(document_miappe,document_data,wd_experience,TimeStamp,prov_dict,ScObj_uri,repertoire_photos,login,silex_API_Client):
    #getting experiment uri
    connexion(login, silex_API_Client)
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    NameExp = dataframe['name'].dropna().iloc[0]
    facility = str(dataframe['facilities'].iloc[0]).replace(",","_").replace(" ","_")
    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)["result"]
    exp_uri = Exp_Src[0].uri
    #GETTING PID
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]

    if 'Angle' not in df_data.columns:
        df_data["Angle"]=None
        console.print("[red]no angle data found in tabular data")
    console.print(f'[bold cyan]PID found:[/bold cyan] {pid}')
    #Liste des images
    wd_img = repertoire_photos
    ls_files = []
    for (root, dirs, files) in os.walk(wd_img):
        for filename in files:
            if filename.endswith(".png"):
                ls_files.append(os.path.join(root, filename))
    ls_fec = [x for x in ls_files if "FishEyeCorrected" in x]
    ls_fem = [x for x in ls_files if "FishEyeMasked" in x ]
    # On récupère également la liste de noms de fichiers présents dans notre tableur de données (uniques et sans les NA)
    if 'FEC_Filename' in df_data.columns:
        data_ls_fec=df_data['FEC_Filename'].dropna().unique().tolist()
    if 'FEM_Filename' in df_data.columns:
        data_ls_fem=df_data['FEM_Filename'].dropna().unique().tolist()
    #On extrait le nom des fichiers pour chaque dossier (fem/fec)
    nom_fichier_fec={os.path.basename(path) for path in ls_fec}
    nom_fichier_fem={os.path.basename(path) for path in ls_fem}
    # je transforme nos listes récupées dans le tableur de données en set pour les comparer à ceux d'au desuss
    set_ls_fec=set(data_ls_fec)
    set_ls_fem=set(data_ls_fem)
    #je fais une soustraction pour chaque cas, comme ça on sait si il manque image, ou lien dans le data sheet
    missing_fec_database=set_ls_fec-nom_fichier_fec
    missing_fem_database=set_ls_fem-nom_fichier_fem
    missing_fec_spreadsheet=nom_fichier_fec-set_ls_fec
    missing_fem_spreadsheet=nom_fichier_fem-set_ls_fem
    #ça c'est juste pour l'affichage, on fait 4 tests pour informer l'utilsateur de ce qui manque
    if len(missing_fec_database)!=0:
        console.print(f"{len(missing_fec_database)} [red]images are missing from the FEC picture database..[/red]")
        if Prompt.ask("show the missing pictures?",choices=["y", "n"], default="y") == "y":
            console.print(missing_fec_database)
    if len(missing_fem_database)!=0:
        console.print(f"{len(missing_fem_database)} [red]images are missing from the FEM picture database..[/red]")
        if Prompt.ask("show the missing pictures?",choices=["y", "n"], default="y") == "y":
            console.print(missing_fem_database)
    if len(missing_fec_spreadsheet)!=0:
        console.print(f"{len(missing_fec_spreadsheet)} [red]images are missing from the FEC data speadsheet..[/red]")
        if Prompt.ask("show the missing filenames?",choices=["y", "n"], default="y") == "y":
            console.print(missing_fec_spreadsheet)
    if len(missing_fem_spreadsheet)!=0:
        console.print(f"{len(missing_fem_spreadsheet)} [red]images are missing from the FEM data speadsheet..[/red]")
        if Prompt.ask("show the missing filenames?",choices=["y", "n"], default="y") == "y":
            console.print(missing_fem_spreadsheet)
    #Si tout va bien on dit que tout va bien
    if len(missing_fec_database) + len(missing_fem_database) + len(missing_fec_spreadsheet)+len(missing_fem_spreadsheet)==0:
        console.print("[green]The image database matches the data, we can continue[/green]")
    else:
        if Prompt.ask("[red]Continue despite decrepancies ? The import might fail..[/red]",choices=["y", "n"], default="n") == "n":
            console.print("[bold red]OK, exiting client ![/bold red]")
            sys.exit()

    console.print(f'[bold cyan]Numbers of FEC Img:[/bold cyan] [bold green]{len(ls_fec)}\n[bold cyan]Numbers of FEM:[/bold cyan] [bold green]{len(ls_fem)}')    
    stop = Prompt.ask("[bold green]Do you want to continue to import images?[/bold green]", choices=["y", "n"], default="y")
    if stop =="n":
        console.print("[bold red]OK, exiting client ![/bold red]")
        sys.exit()
    #Fin de liste des images
    #Pour TESTS
    # sorted_ls_fec=sorted(ls_fec)
    # sorted_ls_fem=sorted(ls_fem)
    # ls_fec = sorted_ls_fec[-6:-1] # On trie les deux listes dans l'ordre AZ puis on prends que les 5/10 derniers (en l'occurence les 5 derniers)
    # ls_fem = sorted_ls_fem[-6:-1] # Et on utilise ça à la place de la giga-liste 
    #print (ls_fec)
    #print (ls_fem) 
    #Pour TESTS

    CamPos,PlantMask=get_round_protocol_info(wd_experience,document_data)
    print("protocol info ok")
    dat_api = silex.DataApi(silex_API_Client)
    #Traitement des images FishEyeCorrected (FEC)do you want
    prov_fec = prov_dict[f'{facility}_{pid}_FishEyeCorrectedImages']
    print("prov_fec ok")
    dict_fec = {os.path.basename(path): path for path in ls_fec if os.path.basename(path) in data_ls_fec}
    dict_fem = {os.path.basename(path): path for path in ls_fem if os.path.basename(path) in data_ls_fem}
    fem_or_fec="fec"
    corr_data = parse_excel_for_metadata(df_data,dict_fec,prov_fec,fem_or_fec)
    print("corrected data ok")
    existing_fec_keys = get_existing_images(dat_api, prov_fec, exp_uri)
    print("existing_corrected_data ok")
    corr_to_upload = [
        img for img in corr_data.values() 
        if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_fec_keys
    ]

    # ####TEST :
    # toutes_fec_triees = sorted(corr_data.values(), key=lambda x: x["Path"])
    
    # # On isole les 5 premières pour le test
    # fec_test_subset = toutes_fec_triees[:2]

    # corr_to_upload = [
    #     img for img in fec_test_subset 
    #     if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_fec_keys
    # ]
    # ###TEST
    # console.print(f"[bold green]{len(corr_data) - len(corr_to_upload)} [cyan]FEC existantes sur[/cyan] {len(corr_data)}[/bold green]")

    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
    
    for img in track(corr_to_upload, description="[bold green]Uploading FEC[/bold green]"):
        if datetime.datetime.now() > timelimit:
            connexion(login, silex_API_Client)
            timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
        #Set up des settings, pour faire en sorte de pouvoir envoyer des images même sans le dossier round_order
        round_order = int(img.get("Round Order"))
        cam_pos_round = CamPos.get(round_order, {}) # Renvoie un dictionnaire vide si le round order n'existe pas
        settings_dict = {}
        if img.get("Angle") is not None:
            settings_dict["Camera Angle"] = img.get("Angle")
        if cam_pos_round.get("height") is not None:
            settings_dict["Camera Height"] = cam_pos_round.get("height")
        if cam_pos_round.get("Offset") is not None:
            settings_dict["Offset"] = cam_pos_round.get("Offset")
        # fin de set up des settings et creation de la description de l'image
        desc = {
            "rdf_type": "vocabulary:RGBImage",
            "date": img["Date"],
            "target": ScObj_uri[img["Plant ID"]],
            "metadata": {"Round Order": round_order},
            "provenance": {
                "uri": img["Prov"],
                "settings": settings_dict,
                "experiments": [exp_uri]
            }
        }
        
        dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])
    #Création du dictionnaire de liaison FEC -> FEM
    fec_uri_map = {
        (elts.target, elts._date): elts.uri
        for elts in dat_api.get_data_file_descriptions_by_search(
            provenances=[prov_fec], experiments=[exp_uri], page_size=100000
        )["result"]
    }

    #Traitement des images FishEyeMasked (FEM)
    prov_fem = prov_dict[f'{facility}_{pid}_FishEyeMaskedImages']
    #mask_data = [parse_image_filename(f, TimeStamp, prov_fem, pid) for f in ls_fem]
    dict_fem = {os.path.basename(path): path for path in ls_fem if os.path.basename(path) in data_ls_fem}
    fem_or_fec="fem"
    mask_data = parse_excel_for_metadata(df_data,dict_fem,prov_fem,fem_or_fec)
    # Association de l'URI parente
    for img in mask_data.values():
        target = ScObj_uri[img["Plant ID"]]
        date = img["Date"].replace('+', '.000+')
        img["Prov_Used"] = fec_uri_map.get((target, date))

    existing_fem_keys = get_existing_images(dat_api, prov_fem, exp_uri)

    mask_to_upload = [
        img for img in mask_data.values()
        if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_fem_keys
    ]

    # # TEST TEST TEST
    # toutes_fem_triees = sorted(mask_data.values(), key=lambda x: x["Path"])
    
    # fem_test_subset = toutes_fem_triees[:2]

    # mask_to_upload = [
    #     img for img in fem_test_subset 
    #     if (ScObj_uri[img["Plant ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), int(img["Round Order"])) not in existing_fem_keys
    # ]
    # # TEST TEST TEST
    console.print(f"[bold green]Found {len(mask_data) - len(mask_to_upload)} [cyan]FEC on[/cyan] {len(mask_data)} total[/bold green]")

    for img in track(mask_to_upload, description="[bold blue]Uploading FEM[/bold blue]"):
        if datetime.datetime.now() > timelimit:
            connexion(login, silex_API_Client)
            timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
            
        round_order = int(img.get("Round Order"))
        if "Angle" in img: 
            settings = {"Camera Angle": img["Angle"]}
        else:
            settings = {"Camera Angle": None}
        if round_order in PlantMask:
            settings.update(PlantMask[round_order])

        desc = {
            "rdf_type": "vocabulary:RGBImage",
            "date": img["Date"],
            "target": ScObj_uri[img["Plant ID"]],
            "metadata": {"Round Order": round_order},
            "provenance": {
                "uri": img["Prov"],
                "prov_used": [{"uri": img["Prov_Used"], "rdf_type": "vocabulary:RGBImage"}] if img.get("Prov_Used") else [],
                "settings": settings,
                "experiments": [exp_uri]
            }
        }
        
        dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

    console.print('[bold green]Suceeded in importing images ![/bold green]')
