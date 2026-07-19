import sys
import opensilexClientToolsPython as silex
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from simple.ui import console, BANNER, MENU_CREATION, menu, choix_repertoire_travail,HELP_MENU
from simple.auth import INSTANCES, get_login,connexion, is_connected,check_connection_internet
from simple.experiment import find_Exp, create_experiment
from simple.data_import import create_factor, create_germplasm, create_sci_obj,create_data
from simple.datafile_import import create_datafiles
from simple.erreurs import NetworkError, SimpleBaseException,AuthenticationError
from simple.systeme_logs import logger

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
    Factors_Levels_uri = None
    Germplasms_uri = None
    ScObj_uri=None
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
                            experiment_ok = create_experiment(document_miappe, choix_dossier, silex_API_Client)

                        elif choix_creation == 2:
                            Germplasms_uri, Species_uri = create_germplasm(document_miappe, silex_API_Client)

                        elif choix_creation == 3: 
                            Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)

                        elif choix_creation == 4:
                            ScObj_uri = create_sci_obj(document_data,document_miappe,silex_API_Client)

                        elif choix_creation == 5:
                            prov_dict=create_datafiles(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client)
                            
                        elif choix_creation == 6:
                            create_data(document_data, document_miappe,login,wd_experience,silex_API_Client)
                        elif choix_creation == 7:
                            experiment_ok = create_experiment(document_miappe, choix_dossier, silex_API_Client)
                            Germplasms_uri, _ = create_germplasm(document_miappe, silex_API_Client)
                            Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)
                            ScObj_uri = create_sci_obj(document_data,document_miappe,silex_API_Client)
                            prov_dict=create_datafiles(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client)
                            create_data(document_data, document_miappe,login,wd_experience,silex_API_Client)
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
            logger.exception("[bold red]Warning, an Unhandled Error was raised[/bold red]")
            console.print("\nPlease try again or check the logs to know what happened...")

        except KeyboardInterrupt:
            logger.info("Manual interruption")
            console.print("[bold green] Goodbye ^^[/bold green]")
            break
