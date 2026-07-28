import os
import pandas as pd
import opensilexClientToolsPython as silex
from simple.auth import connexion
from simple.__init__ import __version__
import datetime
import ast
from simple.systeme_logs import logger
from simple.erreurs import DataImportError

def get_name_space (silex_API_Client):
    ontology_api = silex.OntologyApi(silex_API_Client)
    instance_uri=ontology_api.get_base_uri()["result"]
    name_space_dict=ast.literal_eval(ontology_api.get_name_space()["result"])
    name_space=str([cle for cle, valeur in name_space_dict.items() if valeur == instance_uri])
    name_space_clean=name_space.replace("'","").replace("[","").replace("]","")+":"
    logger.info(f"name space clean : {name_space_clean} & instance uri : {instance_uri}")
    return name_space_clean,instance_uri

def create_factor(document_miappe, silex_API_Client):
    #getting experiment name
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    name_exp = dataframe['name'].dropna().iloc[0]
    #getting factors
    dataframe = pd.read_excel(document_miappe, sheet_name="factors", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    factor_api = silex.FactorsApi(silex_API_Client)
    factors_uri = {}
    factors_levels_uri = {}
    
    exp_api = silex.ExperimentsApi(silex_API_Client)
    exp_search = exp_api.search_experiments(name=name_exp)["result"]
    name_exp_uri = {name_exp: exp_search[0].uri}
    logger.info(name_exp_uri)
    dico_factor={}

    for row in list(dataframe.to_dict('records')):
    
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
        factor_search = factor_api.search_factors(name=factor_name, experiment=name_exp_uri[name_exp])["result"]

        if factor_search:
            factors_uri[factor_name] = factor_search[0].uri
        else:

            DTO_list = [
                silex.FactorLevelCreationDTO(name=lvl["name"], description=lvl["description"])
                for lvl in factor_data["levels"]
            ]

            body = silex.FactorCreationDTO(name=factor_name, levels=DTO_list, experiment=name_exp_uri[name_exp], description=factor_data["description"])
            factor_api.create_factor(body=body)
            factor_search = factor_api.search_factors(name=factor_name, experiment=name_exp_uri[name_exp])["result"]
            factors_uri[factor_name] = factor_search[0].uri

    for fac_uri in factors_uri.values():
        fac_get = factor_api.get_factor_levels(uri=fac_uri)["result"]
        for lvl in fac_get:
            factors_levels_uri[lvl.name] = lvl.uri

    return factors_levels_uri, factors_uri

def create_germplasm(document_miappe, silex_API_Client):

    dataframe = pd.read_excel(document_miappe, sheet_name="germplasm", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    germplasm_api = silex.GermplasmApi(silex_API_Client)
    species_uri = {}
    germplasms_uri = {}
    #on evite les problèmes de lignes vides ou fantome jsp frr
    dataframe = dataframe.dropna(subset=['name'])
    dataframe = dataframe.replace({float('nan'): None})

    for row in list(dataframe.to_dict('records')):
        
        germ_name = row["name"]
        germ_species = row.get("species")
        rdf_type = str(row["rdf_type"])

        if germ_name not in germplasms_uri:
            #On verifie l'existence de l'éspèce si on est sur une ligne Variété
            if germ_species not in species_uri and rdf_type != "vocabulary:Species":
                spec_src = germplasm_api.search_germplasm(name=f"^{germ_species}$", rdf_type="vocabulary:Species")["result"]
                if not spec_src:
                    logger.error(f"The species {germ_species} associated with {germ_name} was not found... Please declare species before varieties and check for typos in the Miappe")
                    raise DataImportError(f"[bold red]\nPlease check if the species you associated with [cyan]{germ_name}[/cyan] in the miappe template is correct \n Tip : You have to declare all the species before the varieties")
                species_uri[germ_species] = spec_src[0].uri
            #On check si notre variété/espèce existe, et si elle existe pas on la crée
            germ_search = germplasm_api.search_germplasm(name=f"^{germ_name}$", rdf_type=rdf_type)["result"]
            if not germ_search:
                if rdf_type != "vocabulary:Species":
                    row.pop('species', None)
                    row['species'] = species_uri[germ_species]
                row['metadata'] = {"Imported with":f"SIMPLE {__version__}"}
                body = silex.GermplasmCreationDTO(**row)
                germplasm_api.create_germplasm(body=body, check_only=False)
                germ_search = germplasm_api.search_germplasm(name=f"^{germ_name}$", rdf_type=rdf_type)["result"]
            germplasms_uri[germ_name] = germ_search[0].uri

    return germplasms_uri, species_uri

def create_sci_obj(document_data,document_miappe,silex_API_Client,status_callback=None):
    # Récupération du excel page experiment
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    name_exp = dataframe['name'].dropna().iloc[0]
    start_exp = dataframe['start_date'].dropna().iloc[0] if 'start_date' in dataframe.columns and not pd.isna(dataframe['start_date'].dropna().iloc[0]) else None
    end_exp = dataframe['end_date'].dropna().iloc[0] if 'end_date' in dataframe.columns and not pd.isna(dataframe['end_date'].dropna().iloc[0]) else None
    bio_mat_type = dataframe['scientific_object_type'].dropna().iloc[0]
    bio_mat_type = list(map(str.strip, bio_mat_type.split(",")))

    df_factors = pd.read_excel(document_miappe, sheet_name="factors", header=1)
    df_factors.drop(df_factors.columns[df_factors.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    # Extract unique factor names as a list
    factors = df_factors['name'].dropna().astype(str).str.strip().unique().tolist()

    # Ici on récupère les données tabulaires pour créer les objets scientifiques.
    df_data = pd.read_excel(document_data)
    # on garde seulement les Plant ID uniques
    df_sci_obj = df_data.drop_duplicates(subset=["Plant ID"])
    relations_generales = []

    # on cherche si l'expérience éxiste pour en extraire l'uri
    exp_search = silex.ExperimentsApi(silex_API_Client).search_experiments(name=name_exp)
    resultats = exp_search.get("result", [])
    if not resultats:
        logger.error(f"Experiment {name_exp} was not found, check if the name is correct or create the experiment before scientific objects")
        raise DataImportError(f"[bold red]This experiment doesn't exist, please check if the name is correct : {name_exp}[/bold red]")
    name_exp_uri = {name_exp: resultats[0].uri}
    logger.info(name_exp_uri)
    # Récupérer un dictionnaire de facteurs levels pour cette experience
    api_response = silex.ExperimentsApi(silex_API_Client).get_available_factors(exp_search["result"][0].uri)
    if api_response["result"]:
        factors_levels_uri = {}
        for resultat in api_response["result"]:
            for factor_level in resultat.levels:
                factors_levels_uri[factor_level.name] = factor_level.uri
    else:
        factors_levels_uri, _ = create_factor(document_miappe, silex_API_Client)

    # création des relations
    if start_exp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasCreationDate", value=start_exp)
        relations_generales.append(relation_temp)
    else:
        logger.warning('Start Date Missing')
        
    if end_exp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasDestructionDate", value=end_exp)
        relations_generales.append(relation_temp)
    else:
        logger.warning('End Date Missing')
        
    if not bio_mat_type:
        logger.error("The column 'Scientific Object RDF Type' in the 'Experiment sheet' is empty")
        raise DataImportError("Scientific Object RDF Type Missing")
    else:
        for biomat in bio_mat_type:
            ontology_api = silex.OntologyApi(silex_API_Client)
            ontology_search = ontology_api.search_sub_classes_of(name=biomat, parent_type="vocabulary:ScientificObject")["result"]
            if ontology_search:
                rdf_type = ontology_search[0].children[0].uri
            else:
                logger.error(f"Scientific Object RDF Type Unknown: {biomat}")
                raise DataImportError(f"Scientific Object RDF Type Unknown: {biomat}")

    sci_obj_api = silex.ScientificObjectsApi(silex_API_Client)
    sci_obj_uri = {}
    dtos_to_export = []
    dico_germplasm = {}
    created_sci_obj = 0
    base_uri_namespace, base_uri = get_name_space(silex_API_Client)
    #JE RECUPERE TOUS LES OBJETS SCIENTIFIQUES LIES A L'EXPERIENCE
    # JE LES METS DANS UN DICTIONNAIRE ET JE VERIFIE CHAQUE Plant ID AVEC LE NOM DANS LE DICTIONNAIRE
    all_existing_objs = sci_obj_api.search_scientific_objects(experiment=name_exp_uri[name_exp], page_size=10000)["result"]
    sci_obj_cache = {obj.name: obj.uri for obj in all_existing_objs}
    #on envoie pour chaque ligne de la df scobj(sans les duplicatas)
    for row in list(df_sci_obj.to_dict('records')):
        plant_id = row["Plant ID"]
        if plant_id in sci_obj_cache:
            sci_obj_uri.update({plant_id: sci_obj_cache[plant_id]})
        else:
            relations_sci_obj = []
            all_factors = []
            #ici on à la logique de vérification des germplasmes dans les objets scientifiques, on vérifie si il est dans la liste des germplasmes connus, et si oui on prends son uri
            if row["Germplasm"]:
                if row["Germplasm"] not in dico_germplasm.keys():
                    germ_search = silex.GermplasmApi(silex_API_Client).search_germplasm(name=f"^{row['Germplasm']}$")["result"]
                    if germ_search:
                        dico_germplasm[row["Germplasm"]] = germ_search[0].uri
                        germplasm_value = dico_germplasm[row["Germplasm"]]
                        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                        relations_sci_obj.append(relation_temp)
                        logger.info(f"Germplasm {row['Germplasm']} found")
                    else:
                        logger.error(f"Germplasm {row['Germplasm']} cannot be found.")
                        raise DataImportError(f"[bold red] Germplasm [cyan]{row['Germplasm']}[/cyan] cannot be found, please check for typos or if they exist.[/bold red]")
                else:
                    germplasm_value = dico_germplasm[row["Germplasm"]]
                    relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                    relations_sci_obj.append(relation_temp)
            #on récupère les uri des niveaux de facteur
            for one_factor in factors:
                if one_factor in row and pd.notna(row[one_factor]):
                    factor_level = str(row[one_factor]).strip()
                    if factor_level and factors_levels_uri is not None:
                        if factor_level not in factors_levels_uri:
                            logger.warning("The factor level was not found. Starting factor import from the MIAPPE document")
                            factors_levels_uri, factors_uri = create_factor(document_miappe, silex_API_Client)
                            
                            if factor_level not in factors_levels_uri:
                                logger.error(f"This factor level : {factor_level} cannot be found.")
                                raise DataImportError(f"[bold red] This factor level : [cyan]{factor_level}[/cyan] cannot be found, please check for typos or if they really exist.[/bold red]")

                        factor_level_value = factors_levels_uri.get(factor_level)
                        all_factors.append(factor_level_value)
                        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasFactorLevel", value=factor_level_value)
                        relations_sci_obj.append(relation_temp)
                else :
                    logger.error(f"No column with the name : {one_factor} can be found in your tabular data file.")
                    raise DataImportError(f"[bold red] This factor cannot be found in the tabular data file : [cyan]{one_factor}[/cyan]\nPlease check for typos in your tabular data or if the column really has the name you declared in the 'factor' sheet of the MIAPPE file.[/bold red]")
            #on concatène les infos générales et les uri des germplasmes/facteurs puis on envoie le body et on le stock dans un dictionnaire
            relations = relations_generales + relations_sci_obj
            body = silex.ScientificObjectCreationDTO(name=row["Plant ID"], rdf_type=rdf_type, relations=relations, experiment=name_exp_uri[name_exp])
            api_resp = sci_obj_api.create_scientific_object(body)
            url_api = api_resp["result"][0]
            ##ATTENTION NE FONCTIONNE QUE SUR LA SANDBOX, DEMANDER A OPENSILEX POUR RENVOYER L'URI DANS L'API
            sci_obj_search = url_api.replace(base_uri, base_uri_namespace) 
            sci_obj_uri.update({row["Plant ID"]: sci_obj_search})
            sci_obj_cache[row["Plant ID"]] = sci_obj_search
            #Ici je stock les données qui m'interessent dans le dto d'avant dans un dictionnaire, que j'écris après dans le excel
            dtos_to_export.append({
                "studyId": body.experiment,
                "obsUnitType": body.rdf_type,
                "obsUnitId": sci_obj_search,
                "externalId": body.name,
                "biologicalMaterialId": germplasm_value if germplasm_value else None,
                "obsUnitFactorValue": all_factors if all_factors else None,
                "Date Import": datetime.datetime.today().strftime('%Y-%m-%d %H:%M'),
            })
            created_sci_obj += 1
            
            if status_callback and (created_sci_obj % 50 == 0 or created_sci_obj == len(df_sci_obj)):
                status_callback(f"[bold green][✓] {created_sci_obj} scientific objects created on {len(df_sci_obj)} total.[/bold green]")
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
        logger.info("The scientific object sheet was successfully created/edited.")
    return sci_obj_uri,created_sci_obj

def get_provenances(document_data,document_miappe,silex_API_Client,create_default=False):

    data_api = silex.DataApi(silex_API_Client)
    dataframe1 = pd.read_excel(document_miappe, sheet_name="data file", header=1)
    dataframe1.drop(dataframe1.columns[dataframe1.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    dataframe1.columns = dataframe1.columns.str.strip()

    datafile_provenance={}
    for row in dataframe1.to_dict('records'):
        datafile_provenance.update({row.get("dataFileLink"): {
            "prov_morpho_parameters":row.get("Tabular Data Provenance"),
            "prov_datafiles1":row.get("Datafiles1 Provenance"),
            "rdf_type_datafile1":row.get("datafile1_rdf_type"),
            "prov_datafiles2":row.get("Datafiles2 Provenance"),
            "rdf_type_datafile2":row.get("datafile2_rdf_type"),
        }})

    prov_dict = {}
    missing_prov=[]
    datafile_name = os.path.basename(document_data)

    for suffix, config in datafile_provenance.items():
        if datafile_name == suffix:
            for prov_name in datafile_provenance[suffix].values():
                if pd.isna(prov_name) or prov_name=="RGBImage" or prov_name=="Archive" :
                    continue

                prov_src = data_api.search_provenance(name=prov_name)["result"]
                if prov_src:
                    prov_dict[prov_name] = prov_src[0].uri
                    logger.info(f"Provenance found : {prov_name} URI: {prov_src[0].uri}")
                else:
                    # Création par default si la provenance n'a pas été crée manuellement
                    if not create_default:
                        missing_prov.append(prov_name)
                    else:
                        logger.info(f"Creating default provenance : {prov_name}")
                        body = silex.ProvenanceCreationDTO(
                            name=prov_name,
                            description="This provenance was created by default using SIMPLE. You may want to add agents, activities etc...",
                            prov_agent=[],
                            prov_activity=[]
                        )

                        data_api.create_provenance(body=body)
                        prov_src = data_api.search_provenance(name=prov_name)["result"]
                        prov_dict[prov_name] = prov_src[0].uri

    return prov_dict,datafile_provenance,missing_prov

def data_mapping(document_data,document_miappe):
    df_data = pd.read_excel(document_data)
    dataframe = pd.read_excel(document_miappe, sheet_name="mapping_table_variables", header=0)
    
    morpho_info = {row["column_in_data_table"]: row["opensilex_variable_name"] for row in dataframe.to_dict('records')}
    morpho_info = {k: v for k, v in morpho_info.items() if k in df_data.columns}
    
    return morpho_info 
    
def create_data(document_data, document_miappe, login, silex_API_Client, morpho_info, prov_dict, datafile_provenance, sci_obj_uri, avancement_upload = None):

    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    name_exp = dataframe['name'].dropna().iloc[0]
    exp_search = silex.ExperimentsApi(silex_API_Client).search_experiments(name=name_exp)
    name_exp_uri = {name_exp: exp_search["result"][0].uri}
    logger.info(name_exp_uri)
    #Gestion provenances
    provenance_morpho = None
    provenance_datafile1 = None
    provenance_datafile2 = None
    rdf_type_2 = None
    rdf_type_1 = None
    datafile_name = os.path.basename(document_data)

    for suffix, config in datafile_provenance.items():
        if datafile_name == suffix:
            provenance_morpho=config.get("prov_morpho_parameters") if not pd.isna(config.get("prov_morpho_parameters")) else None
            provenance_datafile1=config.get("prov_datafiles1") if not pd.isna(config.get("prov_datafiles1")) else None
            rdf1 = config.get("rdf_type_datafile1")
            rdf_type_1 = rdf1 if not pd.isna(rdf1) else None
            provenance_datafile2=config.get("prov_datafiles2") if not pd.isna(config.get("prov_datafiles2")) else None
            rdf2 = config.get("rdf_type_datafile2")
            rdf_type_2 = rdf2 if not pd.isna(rdf2) else None
            break
    
    #FORMATAGE DONNÉES
    timezone_exp = dataframe['experiment_timezone'].dropna().iloc[0] if 'experiment_timezone' in dataframe.columns else 'UTC'
    desired_format = "%Y-%m-%dT%H:%M:%S%z"
    df_data = pd.read_excel(document_data)
    
    # ON RECUPERE LE TEMPS DANS TIMESTAMP ET ON CONVERTI EVENTUELLEMENT
    df_data['Measuring Time'] = pd.to_datetime(df_data['timestamp'], format="%Y-%m-%dT%H:%M:%S%z")
    df_data['Measuring Time'] = df_data['Measuring Time'].dt.tz_localize('UTC').dt.tz_convert(timezone_exp).dt.strftime(desired_format)

    if 'Angle' not in df_data.columns:
        df_data['Angle']=None
    if 'Round Order' not in df_data.columns:
        df_data['Round Order']=None

    # ON TENTE DE RECUPERE LES DONNÉES DES DATAFILES QU'ON A UPLOAD PRECEDEMMENT SI DATAFILE IL Y A
    prov = provenance_datafile2 if provenance_datafile2 is not None else provenance_datafile1
    rdf_type = rdf_type_2 if rdf_type_2 is not None else rdf_type_1
    mask_uri=[]
    data_api = silex.DataApi(silex_API_Client)

    if prov is not None:
        data_search = data_api.get_data_file_descriptions_by_search(provenances=[prov_dict[prov]], experiments=[name_exp_uri[name_exp]], page_size=200000)["result"]
        
        uri_to_trayid = {v: k for k, v in sci_obj_uri.items()}

        for elts in data_search:
                trayid = uri_to_trayid.get(elts.target)
                
                if trayid: # on ajoute seulement si la cible est trouvée
                    mask_uri.append({
                        'Type': 'FEM',
                        "Target": elts.target,
                        "Plant ID": trayid,
                        "Date": elts._date,
                        'Round Order': elts.metadata.get("Round Order") if elts.metadata else None,
                        "Angle": elts.provenance.settings.get("Camera Angle") if elts.provenance.settings else None,
                        "uri": elts.uri
                    })

    #Connexion toutes les 30 mins pour éviter les éventuels kick, mais très peu probable quand même vu la vitesse d'execution :p
    connexion(login, silex_API_Client)
    timelimit = datetime.datetime.now()+datetime.timedelta(minutes=30)
    Var_Api = silex.VariablesApi(silex_API_Client)
    #On recupère en une fois toutes les données tabulaires existantes pour la variable 
    logfile={}
    for key, value in morpho_info.items():
        logfile[value] = []
        nom_colonne=key
        variable_search = Var_Api.search_variables(name=value)["result"]
        all_existing_data = data_api.search_data_list(
            variables=[variable_search[0].uri],
            experiments=[name_exp_uri[name_exp]], 
            page_size=200000 
        )['result']
        existing_data_cache = set()
        if all_existing_data:
            for data in all_existing_data:
                round_order = data.metadata.get('Round Order') if data.metadata else None
                existing_data_cache.add((data.target, data._date, round_order))
        #GET/CREATE NUMERICAL DATA
        pas=4000
        for slc in range(0, len(df_data), pas): 
            df_Slice = df_data.iloc[slc : slc + pas]
            bodies=[]
            for row in df_Slice.to_dict('records'):

                target_uri = sci_obj_uri[row["Plant ID"]]
                formatted_date = str(row['Measuring Time']).replace('+', '.000+')
                round_order_val =row.get('Round Order') if pd.notna(row.get('Round Order')) else None
                
                #VERIFICATION DE L'EXISTENCE DES DONNÉES EN MÉMOIRE
                if (target_uri, formatted_date, round_order_val) in existing_data_cache:
                    logfile[value].append({'Angle': row.get("Angle"), 'Plant ID': {row["Plant ID"]}, 'Round Order': {row.get("Round Order")}})
                else:
                    provenance_used=None
                    setting_dict={"Camera Angle": row["Angle"]}
                    if 'Datafile1_Filename' in df_data.columns or 'Datafile2_Filename' in df_data.columns:
                        for item in mask_uri:
                                if item["Plant ID"]==row["Plant ID"] and item["Date"]==row['Measuring Time'].replace('+', '.000+'):
                                    provenance_used=silex.ProvEntityModel(uri=item["uri"], rdf_type=f"vocabulary:{rdf_type}")
                                    break
                    if pd.notna(row[key]):
                        body = silex.DataCreationDTO(_date = str(row['Measuring Time']),
                                                target = sci_obj_uri[row["Plant ID"]],
                                                variable = variable_search[0].uri,
                                                value = row[key],
                                                metadata = {"Round Order": row.get("Round Order"), "Nom Colonne": nom_colonne,"Imported with":f"SIMPLE {__version__}"},
                                                provenance = silex.DataProvenanceModel(
                                                    uri = prov_dict[provenance_morpho],
                                                    prov_used = [provenance_used] if provenance_used else [],
                                                    settings = setting_dict,
                                                    experiments = [name_exp_uri[name_exp]]))
                        bodies.append(body)
                    if datetime.datetime.now() > timelimit:
                        connexion(login, silex_API_Client)

                        data_api = silex.DataApi(silex_API_Client)
                        timelimit = datetime.datetime.now()+datetime.timedelta(minutes=30)
            if bodies:
                data_api.add_list_data(body=bodies,)
                logger.info(f'{len(bodies)} lines of data from {value} were sucessfully uploaded.')
                if avancement_upload:
                    avancement_upload(value,len(bodies))
            else:
                logger.info(f'all data for {value} was already uploaded')
                if avancement_upload:
                    avancement_upload(value,0)

    logger.info('Data Import complete with sucess')
    return True