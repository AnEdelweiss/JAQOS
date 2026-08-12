import opensilexClientToolsPython as silex
import pandas as pd

from simple.erreurs import DataImportError
from simple.systeme_logs import logger


def api_find_experiment_by_name(silex_API_Client, name_exp):
    exp_api = silex.ExperimentsApi(silex_API_Client)
    exp_data=None
    exp_data = exp_api.search_experiments(name=name_exp)
    if exp_data["result"] :
        logger.info(f"User looked for the experiment : {name_exp}. It exists.")
    else:
        logger.info(f"User looked for the experiment : {name_exp}. It does not exist.")
    return exp_data["result"]


def create_experiment(document_miappe, silex_API_Client, status_callback=None):

    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )

    dataframe["start_date"] = pd.to_datetime(dataframe["start_date"]).dt.strftime("%Y-%m-%d")
    dataframe["end_date"] = pd.to_datetime(dataframe["end_date"]).dt.strftime("%Y-%m-%d")
    
    records = dataframe.where(pd.notnull(dataframe), None).to_dict("records")

    Exp_Api = silex.ExperimentsApi(silex_API_Client)
    Org_Api = silex.OrganizationsApi(silex_API_Client)
    Sec_Api = silex.SecurityApi(silex_API_Client)
    Proj_Api = silex.ProjectsApi(silex_API_Client)

    NameExp_uri = {}
    for row_dict in records:
        NameExp_uri = {}

        # Fonction pour split, strip et retourner un truc vide si la case est vide
        def to_list(key):
            val = row_dict.get(key)
            return [x.strip() for x in str(val).split(",")] if val is not None else []

        # get the info of everythng for the experiment
        NameExp = row_dict.get("name")
        StartExp = row_dict.get("start_date")
        EndExp = row_dict.get("end_date")
        DescriptionExp = row_dict.get("description", "")
        ObjectiveExp = row_dict.get("objective")
        Is_Public = bool(row_dict.get("is_public", True))
        # look for the experiment, if found, no creation !
        Exp_Src = Exp_Api.search_experiments(name=NameExp)["result"]
        if Exp_Src:
            NameExp_uri[NameExp] = Exp_Src[0].uri
            if status_callback:
                status_callback(
                    f"[bold green][✓][/bold green] [bold yellow]An experiment was found with this URI :[/bold yellow]  {NameExp_uri[NameExp]}"
                )
            continue

        if not ObjectiveExp:
            logger.error("Objective Missing From MIAPPE file experiment sheet")
            raise DataImportError("Objective Missing From MIAPPE file experiment sheet")
        if not StartExp:
            logger.error("Starting Date Missing From MIAPPE file experiment sheet")
            raise DataImportError(
                "Starting Date Missing From MIAPPE file experiment sheet"
            )
        if not EndExp:
            logger.warning("Ending Date Missing From MIAPPE file experiment sheet")
        if status_callback:
            status_callback(
                f"[bold green]Start Date:[/bold green] [bold cyan]{StartExp}"
            )
            status_callback(
                f"[bold green]Objective:[/bold green] [bold cyan]{str(ObjectiveExp)[0:400]}..."
            )
            status_callback(
                f"[bold green]Description:[/bold green] [bold cyan]{str(DescriptionExp)[0:400]}...[/bold cyan]"
            )

        # get the lists
        ls_Organisation = to_list("organisations")
        ls_Projects = to_list("projects")
        ls_Facilities = to_list("facilities")
        ls_Scientific_Supervisors = to_list("scientific_supervisors")
        ls_Technical_Supervisors = to_list("technical_supervisors")
        ls_Groups = to_list("groups")

        Organisation_uri = {}
        for organisation in ls_Organisation:
            if organisation is None:
                logger.warning(
                    "Organisation Missing From MIAPPE file experiment sheet"
                )
                ls_Organisation = None
            else:
                Org_Src = Org_Api.search_organizations(pattern=organisation)["result"]
                if Org_Src:
                    Organisation_uri.update({organisation: Org_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{organisation}[/green] URI: {Org_Src[0].uri}"
                        )
                    ls_Organisation = list(Organisation_uri.values())
                else:
                    logger.warning(
                        f"{organisation}: Unknown Organisation "
                    )
                    ls_Organisation = None

        Groups_uri = {}
        for group in ls_Groups:
            if group is None:
                logger.warning(
                    "Group Missing From MIAPPE file experiment sheet"
                )
                ls_Groups = None
            else:
                Sec_Src = Sec_Api.search_groups(name=group)["result"]
                if Sec_Src:
                    Groups_uri.update({group: Sec_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{group}[/green] URI: {Sec_Src[0].uri}"
                        )
                    ls_Groups = list(Groups_uri.values())
                else:
                    logger.warning(f"{group}: Unknown Group")
                    ls_Groups = None
        Projects_uri = {}
        for project in ls_Projects:
            if project is None:
                logger.warning(
                    "[bold yellow]Project Missing From MIAPPE experiment sheet[/bold yellow]"
                )
                ls_Projects = None
            else:
                Proj_Src = Proj_Api.search_projects(name=project)["result"]
                if Proj_Src:
                    Projects_uri.update({project: Proj_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{project}[/green] URI: {Proj_Src[0].uri}"
                        )
                    ls_Projects = list(Projects_uri.values())
                else:
                    logger.warning(f"[bold red]{project}: Unknown Project[/bold red]")
                    ls_Projects = None

        Facilities_uri = {}
        for facility in ls_Facilities:
            if facility is None:
                logger.warning(
                    "[bold yellow]Organisation Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                ls_Facilities = None
            else:
                Org_Src = Org_Api.search_facilities(pattern=facility)["result"]
                if Org_Src:
                    Facilities_uri.update({facility: Org_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{facility}[/green] URI: {Org_Src[0].uri}"
                        )
                    ls_Facilities = list(Facilities_uri.values())
                else:
                    logger.warning(
                        f"[bold red] {facility}: Unknown Facility[/bold red]"
                    )
                    ls_Facilities = None
        Scientific_Supervisors_uri = {}
        for scisup in ls_Scientific_Supervisors:
            if scisup is None:
                logger.warning(
                    "[bold yellow]Scientific Supervisors Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                ls_Scientific_Supervisors = None
            else:
                Sec_Src = Sec_Api.search_persons(name=str(scisup))["result"]
                if Sec_Src:
                    Scientific_Supervisors_uri.update({scisup: Sec_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{scisup}[/green] URI: {Sec_Src[0].uri}"
                        )
                    ls_Scientific_Supervisors = list(
                        Scientific_Supervisors_uri.values()
                    )
                else:
                    logger.warning(
                        f"[bold red]{scisup}: Unknown Scientific Supervisors[/bold red]"
                    )
                    ls_Scientific_Supervisors = None
        Technical_Supervisors_uri = {}
        for techsup in ls_Technical_Supervisors:
            if techsup is None:
                logger.warning(
                    " [bold yellow]Technical Supervisors Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                ls_Technical_Supervisors = None
            else:
                Sec_Src = Sec_Api.search_persons(name=techsup)["result"]
                if Sec_Src:
                    Technical_Supervisors_uri.update({techsup: Sec_Src[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{techsup}[/green] URI: {Sec_Src[0].uri}"
                        )
                    ls_Technical_Supervisors = list(Technical_Supervisors_uri.values())
                else:
                    logger.warning(
                        f"[bold red] {techsup}: Unknown Technical Supervisors[/bold red]"
                    )
                    ls_Technical_Supervisors = None
        body = silex.ExperimentCreationDTO(
            name=NameExp,
            start_date=StartExp,
            end_date=EndExp,
            description=DescriptionExp,
            objective=ObjectiveExp,
            organisations=ls_Organisation,
            projects=ls_Projects,
            facilities=ls_Facilities,
            scientific_supervisors=ls_Scientific_Supervisors,
            technical_supervisors=ls_Technical_Supervisors,
            groups=ls_Groups,
            is_public=Is_Public,
        )

        Exp_Api.create_experiment(body=body)
        logger.info(NameExp_uri)
        Exp_Src = Exp_Api.search_experiments(name=NameExp)
        NameExp_uri.update({NameExp: Exp_Src["result"][0].uri})

    return NameExp_uri
