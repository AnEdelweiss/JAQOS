from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from simple.erreurs import DataImportError
from simple.experiment import api_find_experiment_by_name, create_experiment


class TestExperiment:
    @patch("simple.experiment.silex.ExperimentsApi")
    def test_api_find_experiment_by_name(self, mock_exp_api_class):
        """Test la recherche basique d'une expérience."""
        # 1. Arrange : On prépare notre faux client API
        mock_api_instance = mock_exp_api_class.return_value
        mock_api_instance.search_experiments.return_value = {
            "result": [{"uri": "http://test-uri/exp1"}]
        }

        # 2. Act : On lance la fonction
        result = api_find_experiment_by_name("fake_client", "Mon_Experience")

        # 3. Assert : On vérifie que la recherche a bien été appelée avec le bon nom
        mock_api_instance.search_experiments.assert_called_once_with(
            name="Mon_Experience"
        )
        assert result[0]["uri"] == "http://test-uri/exp1"

    @patch("simple.experiment.pd.read_excel")
    @patch("simple.experiment.silex.ExperimentsApi")
    @patch("simple.experiment.silex.OrganizationsApi")
    @patch("simple.experiment.silex.SecurityApi")
    @patch("simple.experiment.silex.ProjectsApi")
    def test_create_experiment_already_exists(
        self,
        mock_proj_api,
        mock_sec_api,
        mock_org_api,
        mock_exp_api_class,
        mock_read_excel,
    ):
        """Test que si l'expérience existe déjà, le code l'ignore (test du 'continue')."""

        # Faux DataFrame d'entrée
        fake_df = pd.DataFrame(
            [
                {
                    "name": "Exp_Existante",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "objective": "Tester les doublons",
                }
            ]
        )
        mock_read_excel.return_value = fake_df

        # Le Mock de l'API dit : "Oui, j'ai trouvé cette expérience sur le serveur !"
        mock_exp_instance = mock_exp_api_class.return_value
        faux_resultat = MagicMock()
        faux_resultat.uri = "http://test-uri/deja-la"
        mock_exp_instance.search_experiments.return_value = {"result": [faux_resultat]}

        # Un faux callback pour vérifier qu'on envoie bien un message à l'UI
        mock_callback = MagicMock()

        # On exécute la fonction
        result_uris = create_experiment(
            "fake_miappe.xlsx", "fake_client", status_callback=mock_callback
        )

        # VÉRIFICATIONS :
        # 1. On s'assure qu'on a bien récupéré l'URI
        assert result_uris["Exp_Existante"] == "http://test-uri/deja-la"
        # 2. On s'assure que create_experiment N'A JAMAIS été appelé (grâce au 'continue')
        mock_exp_instance.create_experiment.assert_not_called()
        # 3. On s'assure que le callback a bien prévenu l'utilisateur
        assert "An experiment was found with this URI" in mock_callback.call_args[0][0]

    @patch("simple.experiment.pd.read_excel")
    @patch("simple.experiment.silex.ExperimentsApi")
    @patch("simple.experiment.silex.OrganizationsApi")
    @patch("simple.experiment.silex.SecurityApi")
    @patch("simple.experiment.silex.ProjectsApi")
    def test_create_experiment_success(
        self,
        mock_proj_api,
        mock_sec_api,
        mock_org_api,
        mock_exp_api_class,
        mock_read_excel,
    ):
        """Test la création complète d'une nouvelle expérience."""

        # Faux DataFrame d'entrée
        fake_df = pd.DataFrame(
            [
                {
                    "name": "Nouvelle_Exp",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "objective": "Nouvel Objectif",
                    "is_public": True,
                }
            ]
        )
        mock_read_excel.return_value = fake_df

        mock_exp_instance = mock_exp_api_class.return_value

        # Comportement du Mock :
        # 1er appel (search avant création) : Rien trouvé (liste vide)
        # 2ème appel (search après création) : Trouvé
        faux_resultat = MagicMock()
        faux_resultat.uri = "http://test-uri/nouvelle-exp"
        mock_exp_instance.search_experiments.side_effect = [
            {"result": []},
            {"result": [faux_resultat]},
        ]

        # Fausse réponse de création
        mock_exp_instance.create_experiment.return_value = {
            "metadata": {"datafiles": ["success"]}
        }

        # On exécute
        result_uris = create_experiment("fake_miappe.xlsx", "fake_client")

        # Vérification : La fonction de création a bien été appelée !
        mock_exp_instance.create_experiment.assert_called_once()
        assert result_uris["Nouvelle_Exp"] == "http://test-uri/nouvelle-exp"

    @patch("simple.experiment.pd.read_excel")
    @patch("simple.experiment.silex.ExperimentsApi")
    def test_create_experiment_missing_objective(
        self, mock_exp_api_class, mock_read_excel
    ):
        """Test qu'une erreur est levée si l'objectif est manquant."""

        # Faux DataFrame sans objectif (None)
        fake_df = pd.DataFrame(
            [
                {
                    "name": "Exp_Invalide",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "objective": None,  # <-- DONNÉE MANQUANTE
                }
            ]
        )
        mock_read_excel.return_value = fake_df

        mock_exp_instance = mock_exp_api_class.return_value
        mock_exp_instance.search_experiments.return_value = {
            "result": []
        }  # L'expérience n'existe pas

        # On vérifie que la fonction crashe bien avec notre erreur personnalisée
        with pytest.raises(
            DataImportError, match="Objective Missing From MIAPPE file experiment sheet"
        ):
            create_experiment("fake_miappe.xlsx", "fake_client")
