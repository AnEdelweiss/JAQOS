from rich.prompt import Prompt
import sys
import os
import json
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from rich.table import Table
from simple.ui import console,show_data_table_dictionnaire
from simple.auth import connexion
import datetime
from pprint import pprint
import ast

def get_name_space (silex_API_Client):
    ontology_api = silex.OntologyApi(silex_API_Client)
    instance_uri=ontology_api.get_base_uri()["result"]
    name_space_dict=ast.literal_eval(ontology_api.get_name_space()["result"])
    name_space=str([cle for cle, valeur in name_space_dict.items() if valeur == instance_uri])
    name_space_clean=name_space.replace("'","").replace("[","").replace("]","")+":"
    return name_space_clean,instance_uri

def create_factor(document_miappe, silex_API_Client):
    #getting experiment name
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    name_exp = dataframe['name'].dropna().iloc[0]

    #getting factors
    console.print(f"[cyan]Fichier :[/cyan] {document_miappe}")
    dataframe = pd.read_excel(document_miappe, sheet_name="factors", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    fac_api = silex.FactorsApi(silex_API_Client)
    factors_uri = {}
    factors_levels_uri = {}
    
    exp_api = silex.ExperimentsApi(silex_API_Client)
    Exp_Src = exp_api.search_experiments(name=name_exp)["result"]
    name_exp_uri = {name_exp: Exp_Src[0].uri}

    dico_factor={}

    for row in track(list(dataframe.to_dict('records')), description="[green]Importing factors...[/green]"):
    
        factor = str(row["name"]).strip() if pd.notna(row["name"]) else ""
        factor_level = str(row["levels"]).strip() if pd.notna(row["levels"]) else None
        description_factor = row["description"]  if pd.notna(row["description"]) else None
        description_level = row["factor_level_desc"]  if pd.notna(row["factor_level_desc"]) else None

        if factor not in dico_factor:
                    dico_factor[factor] = {"description": description_factor, "levels": []}
                
        if factor_level:
            dico_factor[factor]["levels"].append({
                "name": factor_level, 
                "description": description_level
            })

    for factor_name, factor_data in dico_factor.items():
        Fac_Src = fac_api.search_factors(name=factor_name, experiment=name_exp_uri[name_exp])["result"]

        if Fac_Src:
            factors_uri[factor_name] = Fac_Src[0].uri
        else:

            DTO_list = [
                silex.FactorLevelCreationDTO(name=lvl["name"], description=lvl["description"])
                for lvl in factor_data["levels"]
            ]

            body = silex.FactorCreationDTO(name=factor_name, levels=DTO_list, experiment=name_exp_uri[name_exp], description=factor_data["description"])
            fac_api.create_factor(body=body)
            Fac_Src = fac_api.search_factors(name=factor_name, experiment=name_exp_uri[name_exp])["result"]
            factors_uri[factor_name] = Fac_Src[0].uri

    for fac_uri in factors_uri.values():
        fac_get = fac_api.get_factor_levels(uri=fac_uri)["result"]
        for lvl in fac_get:
            factors_levels_uri[lvl.name] = lvl.uri

    table_name="Factors"
    show_data_table_dictionnaire(table_name,factors_uri)
    table_name="Factor levels"
    show_data_table_dictionnaire(table_name,factors_levels_uri)

    return factors_levels_uri, factors_uri

def create_germplasm(document_miappe, silex_API_Client):

    console.print(f"[cyan]Miappe file :[/cyan] {document_miappe}")
    dataframe = pd.read_excel(document_miappe, sheet_name="germplasm", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    Germ_Api = silex.GermplasmApi(silex_API_Client)
    Species_uri = {}
    Germplasms_uri = {}
    #on evite les problèmes de lignes vides ou fantome jsp frr
    dataframe = dataframe.dropna(subset=['name'])
    dataframe = dataframe.replace({float('nan'): None})

    for row in track(list(dataframe.to_dict('records')), description="[green]Importing germplasms...[/green]"):
        
        germ_name = row["name"]
        germ_species = row.get("species")
        rdf_type = row["rdf_type"]

        if germ_name not in Germplasms_uri:
            #On verifie l'existence de l'éspèce si on est sur une ligne Variété
            if germ_species not in Species_uri and rdf_type != "vocabulary:Species":
                spec_src = Germ_Api.search_germplasm(name=f"^{germ_species}$", rdf_type="vocabulary:Species")["result"]
                if not spec_src:
                    console.print(f"[bold red] Please check if the species you associated with [cyan]{germ_name}[/cyan] in the miappe template is correct \n Tip : You have to declare all the species before the varieties")
                    break
                Species_uri[germ_species] = spec_src[0].uri
            #On check si notre variété/espèce existe, et si elle existe pas on la crée
            Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_name}$", rdf_type=rdf_type)["result"]
            if not Germ_Src:
                if rdf_type != "vocabulary:Species":
                    row.pop('species', None)
                    row['species'] = Species_uri[germ_species]
                body = silex.GermplasmCreationDTO(**row)
                Germ_Api.create_germplasm(body=body, check_only=False)
                Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_name}$", rdf_type=rdf_type)["result"]
            Germplasms_uri[germ_name] = Germ_Src[0].uri

    table_name="Created/Found Germplasms"
    show_data_table_dictionnaire(table_name,Germplasms_uri)

    return Germplasms_uri, Species_uri

def create_sci_obj(document_data,document_miappe,silex_API_Client):
    # Récupération du excel page experiment
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    NameExp = dataframe['name'].dropna().iloc[0]
    StartExp = dataframe['start_date'].dropna().iloc[0]
    EndExp = dataframe['end_date'].dropna().iloc[0]
    BioMat_Type=dataframe['scientifc_object_type'].dropna().iloc[0]
    BioMat_Type=list(map(str.strip, BioMat_Type.split(",")))
    #Ici on récupère les données tabulaires pour créer les objets scientifiques. on choisit de lire du début du doc jusqu'au PID (à adapter)
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]
    console.print(f'[bold cyan]PID found:[/bold cyan] {pid}')
    #on garde seulement les Plant ID uniques
    df_ScObj = df_data.drop_duplicates(subset=["Plant ID"])
    Relations_Gen = []
    #on cherche si l'expérience éxiste pour en extraire l'uri
    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)
    NameExp_uri = {NameExp: Exp_Src["result"][0].uri}
    #Récupérer un dictionnaire de facteurs levels pour cette experience
    api_response = silex.ExperimentsApi(silex_API_Client).get_available_factors(Exp_Src["result"][0].uri, )
    #print(api_response["result"])
    if api_response["result"]:
        factors_levels_uri={}
        for resultat in api_response["result"]:
            for factor_level in resultat.levels :
                factors_levels_uri[factor_level.name]=factor_level.uri
    #console.print(f"facteurs liés à l'experience trouvés : {factors_levels_uri}")
    else :
        factors_levels_uri,_= create_factor(document_miappe, silex_API_Client)

    # création des relations
    if Exp_Src is None:
        console.print(f"[bold red]This experiment doesn't exist, please check if the same is correct : {NameExp}[/bold red]")
        sys.exit()
    #on check les différents points qu'on veut garder pour les metadata des sciobj (start date,end date,material type)
    if StartExp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasCreationDate", value=StartExp)
        Relations_Gen.append(relation_temp)
    else:
        console.print('[bold yellow]Start Date Missing[/bold yellow]')
    if EndExp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasDestructionDate", value=EndExp)
        Relations_Gen.append(relation_temp)
    else:
        console.print('[bold yellow]End Date Missing[/bold yellow]')
    if not BioMat_Type:
        sys.exit("Scientific Object RDF Type Missing")
    else:
        for biomat in BioMat_Type:
            Onto_Api = silex.OntologyApi(silex_API_Client)
            Onto_Src = Onto_Api.search_sub_classes_of(name=biomat, parent_type="vocabulary:ScientificObject")["result"]
            if Onto_Src:
                rdf_type = Onto_Src[0].children[0].uri
            else:
                sys.exit("Scientific Object RDF Type Unknown")
    #on initialise des variables, dont celle qui servira à écrire le excel
    ScObj_Api = silex.ScientificObjectsApi(silex_API_Client)
    ScObj_uri = {}
    dtos_to_export = []
    dico_germplasm={}
    created_sci_obj=0
    base_uri_namespace,base_uri=get_name_space (silex_API_Client)
    #JE RECUPERE TOUS LES OBJETS SCIENTIFIQUES LIES A L'EXPERIENCE
    # JE LES METS DANS UN DICTIONNAIRE ET JE VERIFIE CHAQUE Plant ID AVEC LE NOM DANS LE DICTIONNAIRE
    all_existing_objs = ScObj_Api.search_scientific_objects(experiment=NameExp_uri[NameExp], page_size=10000)["result"]
    scobj_cache = {obj.name: obj.uri for obj in all_existing_objs}
    # print(all_existing_objs)
    # print(scobj_cache)
    #on envoie pour chaque ligne de la df scobj(sans les duplicatas)
    for row in track(list(df_ScObj.to_dict('records')),total=len(df_ScObj), description="[green]Processing Sci_Obj...[/green]"):
        row["Plant ID"] = row["Plant ID"] + ""#test
        tray_id=row["Plant ID"]
        if tray_id in scobj_cache:
            ScObj_uri.update({tray_id: scobj_cache[tray_id]})
        else:
            Relations_ScObj = []
            all_factors=[]
            #ici on à la logique de vérification des germplasmes dans les objets scientifiques, on vérifie si il est dans la liste des germplasmes connus, et si oui on prends son uri
            if row["Germplasm"]:
                if row["Germplasm"] not in dico_germplasm.keys():
                    Germ_Src = silex.GermplasmApi(silex_API_Client).search_germplasm(name=f"^{row["Germplasm"]}$")["result"]
                    if Germ_Src:
                        dico_germplasm[row["Germplasm"]] = Germ_Src[0].uri
                        germplasm_value=dico_germplasm[row["Germplasm"]]
                        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                        Relations_ScObj.append(relation_temp)
                        console.print(f"[bold green]  Germplasm [cyan]{row['Germplasm']}[/cyan] found[/bold green]")
                    else:
                        console.print(f"[bold red] Germplasm [cyan]{row['Germplasm']}[/cyan] cannot be found, please check for typos or if they exist.[/bold red]")
                        console.print("[bold red] Fermeture du client [/bold red]")
                        sys.exit()
                else:
                    germplasm_value=dico_germplasm[row["Germplasm"]]
                    relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                    Relations_ScObj.append(relation_temp)
            #on récupère les uri des niveaux de facteur
            
            if factors_levels_uri and row["Factor Level"]:
                for Factor_level in row["Factor Level"].split(","):
                    Factor_level=Factor_level.strip()
                    if Factor_level not in factors_levels_uri:
                        console.print("[bold red]\n The factor level was not found.\n Starting factor import from the MIAPPE document\n[/bold red]")
                        factors_levels_uri, _ = create_factor(document_miappe, silex_API_Client)
                        
                        if Factor_level not in factors_levels_uri:
                            console.print(f"[bold red] This factor level : [cyan]{Factor_level}[/cyan] cannot be found, please check for typos or if they really exist.[/bold red]")
                            console.print("[bold red] Exiting client [/bold red]")
                            sys.exit()
                    else:
                        factor_level_value = factors_levels_uri.get(Factor_level)
                        all_factors.append(factor_level_value)
                        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasFactorLevel", value=factor_level_value)
                        Relations_ScObj.append(relation_temp)

            #on concatène les infos générales et les uri des germplasmes/facteurs puis on envoie le body et on le stock dans un dictionnaire
            Relations = Relations_Gen + Relations_ScObj
            body = silex.ScientificObjectCreationDTO(name=row["Plant ID"], rdf_type=rdf_type, relations=Relations, experiment=NameExp_uri[NameExp])
            api_resp=ScObj_Api.create_scientific_object(body,)
            url_api=api_resp["result"][0]
            ##ATTENTION NE FONCTIONNE QUE SUR LA SANDBOX, DEMANDER A OPENSILEX POUR RENVOYER L'URI DANS L'API
            ScObj_Src=url_api.replace(base_uri,base_uri_namespace) 
            #ScObj_Src = ScObj_Api.search_scientific_objects(name=row["Plant ID"])["result"]
            #print(ScObj_Src)
            ScObj_uri.update({row["Plant ID"]: ScObj_Src})
            scobj_cache[row["Plant ID"]] = ScObj_Src
            #Ici je stock les données qui m'interessent dans le dto d'avant dans un dictionnaire, que j'écris après dans le excel
            dtos_to_export.append({
                "studyId": body.experiment,
                "obsUnitType": body.rdf_type,
                "obsUnitId": ScObj_Src,
                "externalId": body.name,
                "biologicalMaterialId": germplasm_value if germplasm_value else None,
                "obsUnitFactorValue": all_factors if all_factors else None,
                "Date Import": datetime.datetime.today().strftime('%Y-%m-%d %H:%M'),
            })
            created_sci_obj+=1
    #écriture des metadata des objets scientifiques sur le excel 
    if dtos_to_export:
        dossier_parent = os.path.dirname(document_data)
        fichier_excel = os.path.join(dossier_parent, "output", "miappe_template_filled.xlsx")
        os.makedirs(os.path.dirname(fichier_excel), exist_ok=True)
        df_export = pd.DataFrame(dtos_to_export)
        df_precedent = pd.read_excel(fichier_excel, sheet_name="Observation Unit")
        df_final = pd.concat([df_precedent, df_export])
        with pd.ExcelWriter(fichier_excel, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_final.to_excel(writer, sheet_name="Observation Unit", index=False)
        console.print("[bold green]The scientific object sheet was sucessfuly created/edited.[/bold green]")
    console.print(f"[bold green]End of import : {len(ScObj_uri)-created_sci_obj} found,{created_sci_obj} created. [/bold green]")
    # table_name="Objets sci"
    # show_data_table_dictionnaire(table_name,ScObj_uri)
    return ScObj_uri

def create_provenances(document_data,document_miappe,silex_API_Client):
    #on cherche le MIAPPE pour avoir les facilities( et dans le futur le pid aussi surement)
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    facility = str(dataframe['facilities'].iloc[0]).replace(",","_").replace(" ","_")
    dat_api = silex.DataApi(silex_API_Client)
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]
    prov_dict = {}
    # on décrit les 3 différentes provenances
    provenance_configs = {
        "FishEyeCorrectedImages": {
            "desc": f"Fish-Eye Corrected images acquired by Modular line scan camera ({pid})",
            "activities": [silex.ActivityCreationDTO(rdf_type="vocabulary:ImageAcquisition")],
            "agents": [
                silex.AgentModel(uri="uh:id/device/modular_plantscreen", rdf_type="vocabulary:Actuator"),
                silex.AgentModel(uri=f"uh:id/device/modular_linescan_{pid.lower()}", rdf_type="vocabulary:SensingDevice", settings={})
            ]
        },
        "FishEyeMaskedImages": {
            "desc": f"Fish-Eye Masked images generated by PSI DataAnalyser from Modular line scan ({pid}) images",
            "activities": [silex.ActivityCreationDTO(rdf_type="vocabulary:ImageAnalysis")],
            "agents": [
                silex.AgentModel(uri="uh:id/device/plantscreen_data_analyser", rdf_type="vocabulary:Software"),
                silex.AgentModel(uri=f"uh:id/device/modular_linescan_{pid.lower()}", rdf_type="vocabulary:SensingDevice", settings={})
            ]
        },
        "MorphoParameters": {
            "desc": f"Morphological parameters computed by PSI DataAnalyser from Modular line scan ({pid}) images",
            "activities": [silex.ActivityCreationDTO(rdf_type="vocabulary:ImageAnalysis")],
            "agents": [
                silex.AgentModel(uri="uh:id/device/modular_plantscreen", rdf_type="vocabulary:Actuator"),
                silex.AgentModel(uri=f"uh:id/device/modular_linescan_{pid.lower()}", rdf_type="vocabulary:SensingDevice", settings={}),
                silex.AgentModel(uri="uh:id/device/plantscreen_data_analyser", rdf_type="vocabulary:Software")
            ]
        }
    }

    for suffix, config in provenance_configs.items():
        prov_name = f"{facility}_{pid}_{suffix}"
        # Recherche
        prov_src = dat_api.search_provenance(name=prov_name)["result"]
        
        if prov_src:
            prov_dict[prov_name] = prov_src[0].uri
            console.print(f"[cyan]Provenance found :[/cyan][bold green]{prov_name} [cyan]URI:[/cyan] {prov_src[0].uri}[/bold green]")
        else:
            # Création générique basée sur la configuration
            body = silex.ProvenanceCreationDTO(
                name=prov_name,
                description=config["desc"],
                prov_agent=config["agents"],
                prov_activity=config["activities"]
            )

            api_resp = dat_api.create_provenance(body=body)
            #console.print(f"Provenance Created: {api_resp['metadata']['datafiles']}")
            
            prov_src = dat_api.search_provenance(name=prov_name)["result"]
            prov_dict[prov_name] = prov_src[0].uri
            console.print(f"[cyan]Provenance created :[/cyan][bold green]{prov_name} [cyan] URI:[/cyan] {prov_src[0].uri}[/bold green]")

    #console.print(prov_dict)
    return prov_dict

def create_data(document_data,document_miappe,login,wd_experience,silex_API_Client):
    prov_dict=create_provenances(document_data,document_miappe,silex_API_Client)
    #ON TROUVE LES URI DES OBJETS SCIENTIFIQUES
    ScObj_uri=create_sci_obj(document_data,document_miappe,silex_API_Client)
    #JE RECUPERE LE NOM ET L'URI DE L'ÉXPERIENCE
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    facility = str(dataframe['facilities'].iloc[0]).replace(",","_").replace(" ","_")
    NameExp = dataframe['name'].dropna().iloc[0]
    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)
    NameExp_uri = {NameExp: Exp_Src["result"][0].uri}
    #JE RECUPERE LE PID
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]
    console.print(f'[bold cyan]PID found:[/bold cyan] {pid}')
    # 1. Formatage des données
    desired_format = "%Y-%m-%dT%H:%M:%S%z"
    df_data = pd.read_excel(document_data)
    df_data['Measuring Date'] = df_data['Measuring Date'].dt.date
    df_data['Measuring Time'] = df_data['Measuring Time'].dt.tz_localize('UTC').dt.tz_convert('Europe/Helsinki').dt.strftime(desired_format)
    if 'Angle' not in df_data.columns:
        df_data['Angle']=None
    if 'Round Order' not in df_data.columns:
        df_data['Round Order']=None
    # 2. Lecture du excel
    dataframe = pd.read_excel(document_miappe, sheet_name="mapping_table_variables", header=0)
    Morpho_Info={}
    for row in dataframe.to_dict('records'):
        Morpho_Info[row["column_in_data_table"]]=row["opensilex_variable_name"]
    liste_tabular_data=df_data.columns.tolist()
    # print(liste_tabular_data)
    liste_morpho_info=Morpho_Info.keys()
    # print(liste_morpho_info)
    result = [item for item in liste_morpho_info if item not in liste_tabular_data]#je fais l'union des deux listes pour trouver quelles données importer
    # print (result)
    for i in result: #j'importe seulement les données qui sont présentes dans les colonnes des données tabulaires et dans ma mapping table
        try:
            Morpho_Info.pop(i)
        except Exception:
            continue
    console.print(f"Importating corresponding data found : {Morpho_Info.keys()}")

    stop = Prompt.ask("[bold green]Is this correct?[/bold green]", choices=["y", "n"], default="y")
    if stop =="n":
        console.print("[bold red]OK, exiting client ![/bold red]")
        sys.exit()
        
    # ON RECUPERE LES DONNÉES DES IMAGES QU'ON A UPLOAD PRECEDEMMENT
    prov=f'{facility}_{pid}_FishEyeMaskedImages'

    Dat_Api = silex.DataApi(silex_API_Client)
    Dat_Src = Dat_Api.get_data_file_descriptions_by_search(provenances=[prov_dict[prov]], experiments=[NameExp_uri[NameExp]], page_size=500000)["result"]
    Mask_uri=[]
    for elts in Dat_Src:
        for k, v in ScObj_uri.items():
            if v == elts.target:
                trayid=k

        Mask_uri.append({'Type': 'FEM',
                        "Target": [value for key, value in ScObj_uri.items() if key == trayid][0],
                        "Plant ID": trayid,
                        "Date": elts._date,
                        'Round Order': elts.metadata["Round Order"] if "Round Order" in elts.metadata else None,
                        "Angle": elts.provenance.settings["Camera Angle"] if "Camera Angle" in elts.provenance.settings else None,
                        "uri": elts.uri})
    # print(Mask_uri[0])
    # print(len(Mask_uri))

    prov=f'{facility}_{pid}_MorphoParameters'
    connexion(login, silex_API_Client)

    timelimit = datetime.datetime.now()+datetime.timedelta(minutes=30)

    Dat_Api = silex.DataApi(silex_API_Client)
    Var_Api = silex.VariablesApi(silex_API_Client)

    Prov_Was_Associated_With=silex.ProvEntityModel(uri="uh:id/device/plantscreen_data_analyser",rdf_type="vocabulary:Software")
    logfile={}
    for key, value in Morpho_Info.items():
        logfile[value] = []
        Nom_colonne=key
        Var_Src = Var_Api.search_variables(name=value)["result"]
        #Recuperation des données deja existantes TEST
        all_existing_data = Dat_Api.search_data_list(
            variables=[Var_Src[0].uri],
            experiments=[NameExp_uri[NameExp]], 
            page_size=100000 
        )['result']
        existing_data_cache = set()
        if all_existing_data:
            for data in all_existing_data:
                round_order = data.metadata.get('Round Order') if data.metadata else None
                existing_data_cache.add((data.target, data._date, round_order))
        #Recuperation des données deja existantes TEST

        ## Get or Create Numerical data ###############################################################
        pas=1000
        count=0
        for slc in range(0, len(df_data), pas): 
            df_Slice = df_data.iloc[slc : slc + pas]
            bodies=[]
            count=count+1
            for row in track(df_Slice.to_dict('records'), description=f"importing {value} data"):

                target_uri = ScObj_uri[row["Plant ID"]]
                formatted_date = str(row['Measuring Time']).replace('+', '.000+')
                round_order_val =row.get('Round Order') if pd.notna(row.get('Round Order')) else None
                
                # 3. VÉRIFICATION EN MÉMOIRE
                if (target_uri, formatted_date, round_order_val) in existing_data_cache:
                    logfile[value].append({'Angle': row.get("Angle"), 'Plant ID': {row["Plant ID"]}, 'Round Order': {row.get("Round Order")}})
                else:
                    Prov_Used=None
                    Setting_Dict={"Camera Angle": row["Angle"]}
                    for item in Mask_uri:
                        if 'FEM_Filename' in df_data.columns or 'FEC_Filename' in df_data.columns:
                            if item["Plant ID"]==row["Plant ID"] and item["Date"]==row['Measuring Time'].replace('+', '.000+'):
                                Prov_Used=silex.ProvEntityModel(uri=item["uri"], rdf_type="vocabulary:RGBImage")
                    if pd.notna(row[key]):
                        body = silex.DataCreationDTO(_date = str(row['Measuring Time']),
                                                target = ScObj_uri[row["Plant ID"]],
                                                variable = Var_Src[0].uri,
                                                value = row[key],
                                                metadata = {"Round Order": row.get("Round Order"), "Nom Colonne": Nom_colonne},
                                                provenance = silex.DataProvenanceModel(
                                                    uri = prov_dict[prov],
                                                    prov_used = [Prov_Used] if Prov_Used else [],
                                                    prov_was_associated_with = [Prov_Was_Associated_With],
                                                    settings = Setting_Dict,
                                                    experiments = [NameExp_uri[NameExp]]))
                        bodies.append(body)
                    if datetime.datetime.now() > timelimit:
                        connexion(login, silex_API_Client)

                        Dat_Api = silex.DataApi(silex_API_Client)
                        timelimit = datetime.datetime.now()+datetime.timedelta(minutes=30)
            if bodies:
                #print(bodies)
                Dat_Api.add_list_data(body=bodies,)
                print(f'data from {value} was sucessfully uploaded.')
            else:
                print(f'all data of {value} already uploaded')
    print('Import Over')
