import pytest
from unittest.mock import patch
from simple.cli import main
from simple.erreurs import NetworkError, SimpleBaseException

class TestCLI:

    @patch('simple.cli.console.print')
    @patch('simple.cli.check_connection_internet')
    def test_main_network_error_exits_gracefully(self, mock_check_net, mock_print):
        """
        Vérifie que si l'utilisateur n'a pas internet au lancement, 
        l'application affiche un message propre et s'arrête sans crasher.
        """
        # On simule une coupure internet
        mock_check_net.side_effect = NetworkError("Pas de connexion internet.")
        
        # On lance le main (qui ne devrait pas lever d'erreur technique)
        main()
        
        # On vérifie que le message rouge a bien été affiché
        mock_print.assert_called_with("[bold red]Pas de connexion internet.[/bold red]")

    @patch('simple.cli.connexion')
    @patch('simple.cli.Prompt.ask')
    @patch('simple.cli.IntPrompt.ask')
    @patch('simple.cli.check_connection_internet')
    def test_main_exit_option_9(self, mock_check_net, mock_int_prompt, mock_prompt, mock_connexion):
        """
        Vérifie que taper '9' dans le menu principal quitte bien l'application.
        """
        # On simule l'utilisateur tapant '9'
        mock_int_prompt.return_value = 9
        
        # Le sys.exit(0) va lever l'exception interne SystemExit. 
        # On vérifie que cette sortie est bien déclenchée.
        with pytest.raises(SystemExit) as excinfo:
            main()
            
        assert excinfo.value.code == 0

    @patch('simple.cli.console.print')
    @patch('simple.cli.ui_find_experiment')
    @patch('simple.cli.is_connected')
    @patch('simple.cli.connexion')
    @patch('simple.cli.Prompt.ask')
    @patch('simple.cli.IntPrompt.ask')
    @patch('simple.cli.check_connection_internet')
    def test_main_catches_simple_base_exception(self, mock_check_net, mock_int_prompt, mock_prompt, 
                                                mock_connexion, mock_is_connected, mock_ui_find, mock_print):
        """
        LE TEST LE PLUS IMPORTANT : Le filet de sécurité.
        On vérifie qu'une erreur métier ne casse pas la boucle infinie de l'UI.
        """
        # On simule un utilisateur connecté
        mock_is_connected.return_value = True
        
        # Le scénario : L'utilisateur tape '2' (recherche), ça plante, puis il tape '9' (quitter)
        mock_int_prompt.side_effect = [2, 9]
        
        # On simule une erreur métier (ex: annulation ou donnée introuvable)
        mock_ui_find.side_effect = SimpleBaseException("L'expérience est introuvable.")
        
        # On lance le test et on s'attend à ce qu'il se termine via le choix '9' (SystemExit)
        with pytest.raises(SystemExit):
            main()
            
        # On vérifie que le filet de sécurité a bien attrapé l'erreur et affiché l'alerte jaune
        mock_print.assert_any_call("[bold yellow] \n Warning : L'expérience est introuvable. [/bold yellow]")

    @patch('simple.cli.ui_create_experiment')
    @patch('simple.cli.choix_repertoire_travail')
    @patch('simple.cli.is_connected')
    @patch('simple.cli.connexion')
    @patch('simple.cli.Prompt.ask')
    @patch('simple.cli.IntPrompt.ask')
    @patch('simple.cli.check_connection_internet')
    def test_main_submenu_experiment_creation(self, mock_check_net, mock_int_prompt, mock_prompt, 
                                              mock_connexion, mock_is_connected, mock_choix_rep, mock_ui_create):
        """
        Vérifie que la navigation dans les sous-menus déclenche bien les bonnes fonctions UI.
        """
        mock_is_connected.return_value = True
        
        # On simule un faux retour pour le choix du répertoire
        mock_choix_rep.return_value = ("wd_path", "dossier_test", "miappe.xlsx", "data.csv", "photos/")
        
        # Scénario clavier : 
        # 1. Choix 3 (Menu importation)
        # 2. Choix 1 (Créer expérience)
        # 3. Choix 9 (Quitter le sous-menu)
        # 4. Choix 9 (Quitter l'application)
        mock_int_prompt.side_effect = [3, 1, 9, 9]
        
        with pytest.raises(SystemExit):
            main()
            
        # On vérifie que la fonction enveloppe d'UI a bien été appelée avec le bon fichier
        mock_ui_create.assert_called_once_with("miappe.xlsx", mock_connexion.call_args[0][1] if mock_connexion.call_args else None)