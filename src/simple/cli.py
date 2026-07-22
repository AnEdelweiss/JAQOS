import sys
import opensilexClientToolsPython as silex
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from simple.ui import console, BANNER, MENU_CREATION, menu, choix_repertoire_travail,HELP_MENU
from simple.auth import INSTANCES, get_login,connexion, is_connected,check_connection_internet
from simple.experiment import find_Exp, create_experiment
from simple.data_import import create_sci_obj,create_data,create_factor,create_germplasm,get_provenances,data_mapping
from simple.ui import show_data_table_dictionnaire
from simple.datafile_import import execute_datafiles_upload,check_for_datafiles,get_round_protocol_info
from simple.erreurs import NetworkError, SimpleBaseException,AuthenticationError
from simple.systeme_logs import logger

def ui_import_factor(document_miappe, silex_API_Client):
    console.print(f"[cyan]Miappe file :[/cyan] {document_miappe}")
    logger.info(f"Miappe file : {document_miappe}")

    with console.status("[green]Importing factors to OpenSilex...[/green]", spinner="aesthetic"):
        factors_levels_uri, factors_uri = create_factor(document_miappe, silex_API_Client)

    logger.info(f"{factors_uri},\n{factors_uri}")
    show_data_table_dictionnaire("Factors",factors_uri)
    show_data_table_dictionnaire("Factor levels",factors_levels_uri)

    return factors_levels_uri, factors_uri

def ui_import_germplasm(document_miappe, silex_API_Client):
    console.print(f"[cyan]Miappe file :[/cyan] {document_miappe}")
    logger.info(f"Miappe file : {document_miappe}")

    with console.status("[green]Importing germplasms to OpenSilex...[/green]", spinner="aesthetic"):
        germplasms_uri, species_uri = create_germplasm(document_miappe, silex_API_Client)
        
    logger.info(f"{germplasms_uri},\n{species_uri}")
    show_data_table_dictionnaire("Created/Found Germplasms",germplasms_uri)

    return germplasms_uri,species_uri

def ui_import_sci_obj(document_data,document_miappe,silex_API_Client):

    with console.status("[green]Importing/Searching Scientific objects on OpenSilex instance...[/green]", spinner="aesthetic"):
        sci_obj_uri,created_sci_obj = create_sci_obj(document_data, document_miappe, silex_API_Client)
    found_sci_obj=len(sci_obj_uri)-created_sci_obj

    console.print(f"[bold green]End of search : {found_sci_obj} found,{created_sci_obj} created. [/bold green]")
    if created_sci_obj>0:
        console.print("Scientific object sheet was sucessfully modified in the output MIAPPE")

    logger.info(len(sci_obj_uri))
    logger.info(sci_obj_uri)

    return sci_obj_uri

def ui_import_data(document_data, document_miappe,login,silex_API_Client):

    #on apelle data_mapping pour faire le lien noms colonnes données tabulaires -> variables phis
    with console.status("[green]Checking variable map...[/green]", spinner="aesthetic"):
        morpho_info=data_mapping(document_data, document_miappe)
    console.print(f"[cyan]Corresponding data found :[/cyan] [bold green]{list(morpho_info.keys())}[/bold green]")
    stop = Prompt.ask("[bold green]Would you like to import these data?[/bold green]", choices=["y", "n"], default="y")
    if stop == "n":
        raise SimpleBaseException("Data import cancelled by the user.")

    # on s'occupe des provenances et du retour console s'il en manque etc...
    with console.status("[green]Checking provenances...[/green]", spinner="aesthetic"):
        prov_dict, datafile_provenance, missing_provs = get_provenances(document_data, document_miappe, silex_API_Client)
    if missing_provs:
        console.print(f"[bold red]The following provenances were not found : {missing_provs}[/bold red]")
        create_def = Prompt.ask("[bold yellow]Do you want to create default ones using these names?\n (It is recommended to create them on your PHIS instance manually and then reference them on the MIAPPE in the 'Data Files' sheet) [/bold yellow]", choices=["y", "n"], default="n")
        
        if create_def == "n":
            raise SimpleBaseException("Action cancelled. Please edit your MIAPPE file or create provenances manually.")
            
        with console.status("[green]Creating default provenances...[/green]", spinner="aesthetic"):
            prov_dict, datafile_provenance, _ = get_provenances(document_data, document_miappe, silex_API_Client, create_default=True)
    show_data_table_dictionnaire("Provenances",prov_dict)
    console.print("[bold green] Provenances are OK !")

    # on récupère le dictionnaire d'objets scientifiques
    sci_obj_uri = ui_import_sci_obj(document_data, document_miappe, silex_API_Client)

    def afficher_progres(nom_variable, nb_lignes):

        if nb_lignes > 0:
            console.print(f"[bold cyan] ↳ Succès : {nb_lignes} lignes de données ajoutées pour [green]{nom_variable}[/green][/bold cyan]")
        else:
            console.print(f"[dim white] ↳ Ignoré : Les données pour {nom_variable} étaient déjà présentes.[/dim white]")

    try:
        with console.status("[green]Uploading data to OpenSilex... This will be quick.[/green]", spinner="aesthetic"):
            create_data(document_data, document_miappe, login, silex_API_Client, morpho_info, prov_dict, datafile_provenance, sci_obj_uri, avancement_upload = afficher_progres)
 
    except Exception as e :
        logger.error("Import Failed : This is probably because one of the variable you declared in the MIAPPE 'mapping table' sheet was not found on your Phis instance \nPlease check the sheet for typos or check that the variable really exists. ")

        raise SimpleBaseException(f"Error during import : {e}")

    console.print("[bold green]Data Import Over![/bold green]")

def ui_import_datafiles(document_miappe, document_data, wd_experience, repertoire_photos, login, silex_API_Client):

    #taking care of provenances
    with console.status("[green]Checking provenances...[/green]", spinner="aesthetic"):
        prov_dict, datafile_provenance, missing_provs = get_provenances(document_data, document_miappe, silex_API_Client)
    if missing_provs:
        console.print(f"[bold red]The following provenances were not found : {missing_provs}[/bold red]")
        create_def = Prompt.ask("[bold yellow]Do you want to create default ones using these names?\n (It is recommended to create them on your PHIS instance manually and then reference them on the MIAPPE in the 'Data Files' sheet) [/bold yellow]", choices=["y", "n"], default="n")
        
        if create_def == "n":
            raise SimpleBaseException("Action cancelled. Please edit your MIAPPE file or create provenances manually.")
            
        with console.status("[green]Creating default provenances...[/green]", spinner="aesthetic"):
            prov_dict, datafile_provenance, _ = get_provenances(document_data, document_miappe, silex_API_Client, create_default=True)

    show_data_table_dictionnaire("Provenances",prov_dict)
    console.print("[bold green] Provenances are OK !")

    #getting scientific object uris etc...
    with console.status("[green]Importing/Searching Scientific objects on OpenSilex instance...[/green]", spinner="aesthetic"):
        sci_obj_uri, created_sci_obj = create_sci_obj(document_data, document_miappe, silex_API_Client)

    found_sci_obj=len(sci_obj_uri)-created_sci_obj
    console.print(f"[bold green]End of search : {found_sci_obj} found,{created_sci_obj} created. [/bold green]")

    #getting cam_pos and plant_mask
    with console.status("[green]Looking for camera position and plant mask info[/green]", spinner="aesthetic"):
        cam_pos, plant_mask, protocol_found = get_round_protocol_info(wd_experience, document_data)

    if not protocol_found:
        stop = Prompt.ask("[bold red][X] PlantMask and Camera Position were not found, do you want to continue?\nThis is not a problem if your instance does not use round protocol info..[/bold red]", choices=["y", "n"], default="y")
        if stop == "n":
            raise SimpleBaseException("User cancelled import at Round protocol phase.")
    else:
        console.print("[bold green][✓] PlantMask and Camera Position Info found ![/bold green]")

    #on compare les datafiles et ceux données dans les données tabulaires
    with console.status("Comparing datafile database and tabular data filenames..."):
        dict_datafile1, missing_datafile1, dict_datafile2, missing_datafile2, has_datafile2, df_data = check_for_datafiles(document_data, repertoire_photos)
    
    if missing_datafile1:
        console.print(f"{len(missing_datafile1)} [red][X] datafiles are missing from the datafile1 database.[/red]")
        if Prompt.ask("Show the missing pictures?", choices=["y", "n"], default="y") == "y":
            console.print(missing_datafile1)
            
    if missing_datafile2:
        console.print(f"{len(missing_datafile2)} [red][X] datafiles are missing from the datafile2 database.[/red]")
        if Prompt.ask("Show the missing pictures?", choices=["y", "n"], default="y") == "y":
            console.print(missing_datafile2)

    if missing_datafile1 or missing_datafile2:
        if Prompt.ask("[red]Continue despite discrepancies ? The import may fail...[/red]", choices=["y", "n"], default="n") == "n":
            raise SimpleBaseException("User cancelled action after database discrepancies were found.")
    else:
        console.print("[green][✓] The datafile database matches the data, we can continue[/green]")

    stop = Prompt.ask("[bold green]Do you want to continue to import datafiles?[/bold green]", choices=["y", "n"], default="y")
    if stop == "n":
        raise SimpleBaseException("User aborted datafile import")

    #enfin on téléverse :
    def afficher_statut_tel(mess):
        console.print(f"[bold cyan][+][bold cyan][bold green]{mess}[/bold green]")

    try:
        
        execute_datafiles_upload(
        document_miappe,
        document_data,
        df_data,
        dict_datafile1,
        dict_datafile2,
        has_datafile2,
        prov_dict,
        datafile_provenance,
        sci_obj_uri,
        cam_pos,
        plant_mask,
        login,
        silex_API_Client,
        status_callback=afficher_statut_tel,
        progress_callback=None 
    )
        console.print('[bold green][✓] Succeeded in importing datafiles ![/bold green]')
    except Exception as e:
        logger.exception("Datafile upload failed")
        raise SimpleBaseException("An error occurred during datafile upload.")

def main():
    try:
        check_connection_internet()
    except NetworkError as e:
        console.print(f"[bold red]{e}[/bold red]")
        return
    console.print(BANNER)
    console.print('[bold][green]______________________________________________________________________________________[/green][/bold]\n')
    Prompt.ask("Press a key to start")
    # INITIALISATION DES VARIABLES et de l'api ~
    choix_dossier = None
    document_miappe = None
    wd_experience = None
    #setting default login, here guest on sandbox
    login={
        "identifier":"guest@opensilex.org",
        "password":"guest",
        "host":"https://opensilex.org/sandbox/rest"
        }
    silex_API_Client = silex.ApiClient(verbose=False)
    # CONNECTING AS GUEST ON THE SANDBOX BY DEFAULT ~
    connexion(login,silex_API_Client)
    etat = f"[cyan]Logged in as[/cyan] [bold green]{login["identifier"]}[/bold green] [cyan]on[/cyan] [bold green]{INSTANCES[login["host"]]}[/bold green]."
    #BOUCLE PRINCIPALE
    while True:
        try:
            menu(etat)
            user_input = IntPrompt.ask("[green]\\[+][/green] [cyan]What would you like to do?[/cyan]")
            
            if user_input == 9:
                sys.exit(0)

            elif user_input == 1:
                login= get_login()
                try:
                    connexion(login, silex_API_Client)
                    etat = f"[cyan]Your are logged in as[/cyan] [bold green]{login['identifier']}[/bold green] [cyan]on[/cyan] [bold green]{INSTANCES[login['host']]}[/bold green]."
                except AuthenticationError as e:
                    etat = "[bold red]You are not logged in, please try again...[/bold red]"
                    console.print(e)

            elif user_input == 2:
                if is_connected(silex_API_Client):
                    find_Exp(silex_API_Client)
                else:
                    console.print("[red]Please try to log in first.[/red]")

            elif user_input == 3:
                if is_connected(silex_API_Client):
                    #Gestion du repertoire de travail
                    if choix_dossier:
                        changement_repertoire = Prompt.ask(f"Would you like to continue to work on this experiment ? [bold]{choix_dossier}[/bold] ?", choices=["y", "n"], default="y")
                        if changement_repertoire == 'n':
                            wd_experience, choix_dossier, document_miappe,document_data,repertoire_photos = choix_repertoire_travail()
                    else:
                        console.print("[cyan]You chose to import data on OpenSilex[/cyan]")
                        result = choix_repertoire_travail()
                        if result[0] is not None:
                            wd_experience, choix_dossier, document_miappe,document_data,repertoire_photos = result
                        else:
                            break
                    if not wd_experience:
                        break
                    while True:
                        if choix_dossier is None:
                            console.print("[cyan]You chose to import data on OpenSilex[/cyan]")
                            wd_experience, choix_dossier, document_miappe,document_data,repertoire_photos = choix_repertoire_travail()
                        #Gestion du repertoire de travail
                        console.print(Panel(MENU_CREATION, title="[bold]Experiment Menu[/bold]", border_style="green"))
                        choix_creation = IntPrompt.ask("[green]Please make your choice[/green]")

                        if choix_creation == 1:
                            create_experiment(document_miappe, choix_dossier, silex_API_Client)

                        elif choix_creation == 2:
                            ui_import_germplasm(document_miappe, silex_API_Client)

                        elif choix_creation == 3: 
                            ui_import_factor(document_miappe, silex_API_Client)

                        elif choix_creation == 4:
                            ui_import_sci_obj(document_data,document_miappe,silex_API_Client)

                        elif choix_creation == 5:
                            ui_import_datafiles(document_miappe, document_data, wd_experience, repertoire_photos, login, silex_API_Client)
                            
                        elif choix_creation == 6:
                            ui_import_data(document_data, document_miappe,login,silex_API_Client)

                        elif choix_creation == 7:

                            create_experiment(document_miappe, choix_dossier, silex_API_Client)
                            ui_import_germplasm(document_miappe, silex_API_Client)
                            ui_import_factor(document_miappe, silex_API_Client)
                            create_sci_obj(document_data,document_miappe,silex_API_Client)
                            ui_import_datafiles(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client)
                            ui_import_data(document_data, document_miappe,login,silex_API_Client)
                            break

                        elif choix_creation == 9:
                            break
                else:
                    console.print("[bold red]Your are not logged in[/bold red]")
            elif user_input == 4:
                console.print(Panel(HELP_MENU, title="[bold]Help Menu[/bold]", border_style="yellow", expand=False))
                Prompt.ask("Press any key to go back to the main menu")
            elif user_input in [5, 6, 7, 8]:
                print("under development")
            else:
                print("Invalid input")

        except SimpleBaseException as e:
            logger.warning(f"Action interrupted : {e} ")
            console.print(f"[bold yellow] \n Warning : {e} [/bold yellow]")

        except Exception as e:
            logger.exception(f"[bold red]Warning, an Unhandled Error was raised {e}[/bold red]")
            console.print("\nPlease try again or check the logs to know what happened...")

        except KeyboardInterrupt:
            logger.info("Manual interruption")
            console.print("\n[bold green] Goodbye ^^[/bold green]")
            break
