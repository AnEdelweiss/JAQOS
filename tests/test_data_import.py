import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from simple.data_import import data_mapping, create_data
# Assurez-vous d'importer vos propres modules correctement selon l'arborescence de votre projet
from simple.erreurs import DataImportError
from simple.data_import import (
    create_germplasm,
    create_factor,
    get_provenances,
    create_sci_obj
)

class TestDataImport:
    
    # ==========================================
    # TESTS POUR CREATE_GERMPLASM
    # ==========================================
    
    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.silex.GermplasmApi')
    def test_create_germplasm_success(self, MockGermplasmApi, mock_read_excel):
        """Teste que la création de germplasme fonctionne et renvoie les bons URIs"""
        # 1. Arrange : Préparation des fausses données
        fake_df = pd.DataFrame({
            "name": ["Zea mays", "Apache"],
            "species": [None, "Zea mays"],
            "rdf_type": ["vocabulary:Species", "vocabulary:Variety"]
        })
        mock_read_excel.return_value = fake_df
        
        # Configuration du faux client API et de sa réponse
        mock_api_instance = MockGermplasmApi.return_value
        # On simule que la recherche trouve bien l'espèce et la variété, renvoyant de fausses URIs
        mock_result = MagicMock()
        mock_result.uri = "http://fake-uri.com/germplasm/123"
        mock_api_instance.search_germplasm.return_value = {"result": [mock_result]}
        
        fake_client = MagicMock()
        
        # 2. Act : Exécution de la fonction
        germplasms_uri, species_uri = create_germplasm("dummy_path.xlsx", fake_client)
        
        # 3. Assert : Vérifications
        assert "Zea mays" in germplasms_uri
        assert "Apache" in germplasms_uri
        assert mock_api_instance.create_germplasm.called is False # Car search_germplasm a trouvé des résultats

    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.silex.GermplasmApi')
    def test_create_germplasm_missing_species_raises_error(self, MockGermplasmApi, mock_read_excel):
        """Teste qu'une erreur est levée si on déclare une variété sans avoir déclaré l'espèce avant"""
        fake_df = pd.DataFrame({
            "name": ["Apache"],
            "species": ["Espece_Inconnue"],
            "rdf_type": ["vocabulary:Variety"]
        })
        mock_read_excel.return_value = fake_df
        
        mock_api_instance = MockGermplasmApi.return_value
        # On simule un "404 Not Found" (liste vide) quand l'API cherche l'espèce
        mock_api_instance.search_germplasm.return_value = {"result": []}
        
        fake_client = MagicMock()
        
        # On vérifie que la fonction lève bien notre exception personnalisée avec le bon message
        with pytest.raises(DataImportError) as error_info:
            create_germplasm("dummy_path.xlsx", fake_client)
            
        assert "Apache" in str(error_info.value) # Vérifie que la variété fautive est citée dans l'erreur

    # ==========================================
    # TESTS POUR CREATE_FACTOR
    # ==========================================

    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.silex.FactorsApi')
    def test_create_factor_success(self, MockFactorsApi, MockExpApi, mock_read_excel):
        """Teste la lecture et la création des facteurs"""
        
        # On doit simuler deux appels à read_excel (sheet_name="experiment" puis "factors")
        df_exp = pd.DataFrame({"name": ["Exp_Test"]})
        df_factors = pd.DataFrame({
            "name": ["Watering", "Watering"],
            "levels": ["High", "Low"],
            "description": ["Water factor", "Water factor"],
            "factor_level_desc": ["Lots of water", "Little water"]
        })
        mock_read_excel.side_effect = [df_exp, df_factors]
        
        # Configuration des Mocks API
        mock_exp_instance = MockExpApi.return_value
        mock_exp_result = MagicMock()
        mock_exp_result.uri = "http://fake-uri.com/exp/1"
        mock_exp_instance.search_experiments.return_value = {"result": [mock_exp_result]}
        
        mock_factor_instance = MockFactorsApi.return_value
        # On simule que le facteur n'existe pas encore (retourne vide au 1er appel)
        # puis retourne une fausse URI après sa création
        mock_factor_result = MagicMock()
        mock_factor_result.uri = "http://fake-uri.com/factor/1"
        mock_factor_instance.search_factors.side_effect = [{"result": []}, {"result": [mock_factor_result]}]
        
        # Simulation du get_factor_levels
        mock_lvl_result = MagicMock()
        mock_lvl_result.name = "High"
        mock_lvl_result.uri = "http://fake-uri.com/factor/level/high"
        mock_factor_instance.get_factor_levels.return_value = {"result": [mock_lvl_result]}
        
        fake_client = MagicMock()
        
        factors_levels_uri, factors_uri = create_factor("dummy.xlsx", fake_client)
        
        assert "High" in factors_levels_uri
        assert factors_levels_uri["High"] == "http://fake-uri.com/factor/level/high"
        assert mock_factor_instance.create_factor.called is True

    # ==========================================
    # TESTS POUR GET_PROVENANCES
    # ==========================================

    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.silex.DataApi')
    @patch('simple.data_import.os.path.basename')
    def test_get_provenances_with_missing_and_default_creation(self, mock_basename, MockDataApi, mock_read_excel):
        """Teste que les provenances manquantes sont créées si create_default=True"""
        df_datafile = pd.DataFrame({
            "dataFileLink": ["my_data.xlsx"],
            "Tabular Data Provenance": ["Prov_Test"],
            "Datafiles1 Provenance": [None],
            "datafile1_rdf_type": [None],
            "Datafiles2 Provenance": [None],
            "datafile2_rdf_type": [None]
        })
        mock_read_excel.return_value = df_datafile
        mock_basename.return_value = "my_data.xlsx"
        
        mock_data_api = MockDataApi.return_value
        
        # On simule que la provenance "Prov_Test" n'existe pas la première fois, 
        # puis qu'elle est retournée après sa création par défaut
        mock_prov = MagicMock()
        mock_prov.uri = "http://fake-uri.com/prov/1"
        mock_data_api.search_provenance.side_effect = [{"result": []}, {"result": [mock_prov]}]
        
        fake_client = MagicMock()
        
        # Appel avec create_default=True
        prov_dict, datafile_provenance, missing_prov = get_provenances(
            "dummy_data.xlsx", "dummy_miappe.xlsx", fake_client, create_default=True
        )
        
        assert "Prov_Test" in prov_dict
        assert mock_data_api.create_provenance.called is True
        assert len(missing_prov) == 0 # Car elle a été créée par défaut



    # ==========================================
    # TESTS POUR DATA_MAPPING
    # ==========================================

    @patch('simple.data_import.pd.read_excel')
    def test_data_mapping_success(self, mock_read_excel):
        """Teste que le mapping lie correctement les colonnes présentes et ignore les absentes"""
        # 1. Arrange : Le DataFrame des données n'a que 'Plant ID' et 'Taille'
        df_data = pd.DataFrame(columns=["Plant ID", "Measuring Date", "Taille"])
        
        # Le DataFrame MIAPPE déclare 'Taille' et 'Poids'
        df_miappe = pd.DataFrame({
            "column_in_data_table": ["Taille", "Poids"],
            "opensilex_variable_name": ["var_taille", "var_poids"]
        })
        
        # On simule la lecture des deux fichiers
        mock_read_excel.side_effect = [df_data, df_miappe]
        
        # 2. Act
        morpho_info = data_mapping("dummy_data.xlsx", "dummy_miappe.xlsx")
        
        # 3. Assert : 'Taille' doit être mappé, mais 'Poids' doit être ignoré car absent des données
        assert "Taille" in morpho_info
        assert morpho_info["Taille"] == "var_taille"
        assert "Poids" not in morpho_info

    # ==========================================
    # TESTS POUR CREATE_DATA (DONNÉES TABULAIRES)
    # ==========================================

    @patch('simple.data_import.connexion') # On simule la connexion de sécurité
    @patch('simple.data_import.silex.DataApi')
    @patch('simple.data_import.silex.VariablesApi')
    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.os.path.basename')
    def test_create_data_success_upload(self, mock_basename, mock_read_excel, MockExpApi, MockVarApi, MockDataApi, mock_connexion):
        """Teste l'envoi de nouvelles données tabulaires à l'API"""
        # 1. Arrange
        df_miappe = pd.DataFrame({"name": ["Exp_Test"]})
        
        # Fausses données avec des dates pandas comme attendu
        fake_time = pd.Timestamp('2023-01-01 10:00:00')
        df_data = pd.DataFrame({
            "Plant ID": ["Plant_1", "Plant_2"],
            "timestamp": [fake_time, fake_time],
            "Angle": [45, 90],
            "Round Order": [1, 1],
            "Taille": [15.5, 20.0]
        })
        mock_read_excel.side_effect = [df_miappe, df_data]
        mock_basename.return_value = "dummy_data.xlsx"

        # Configuration des Mocks API
        fake_client = MagicMock()
        
        # Expérience
        mock_exp = MagicMock()
        mock_exp.uri = "http://fake-uri.com/exp/1"
        MockExpApi.return_value.search_experiments.return_value = {"result": [mock_exp]}
        
        # Variable
        mock_var = MagicMock()
        mock_var.uri = "http://fake-uri.com/var/taille"
        MockVarApi.return_value.search_variables.return_value = {"result": [mock_var]}
        
        # Data API : On simule qu'aucune donnée n'existe encore pour déclencher l'upload
        mock_data_api_instance = MockDataApi.return_value
        mock_data_api_instance.search_data_list.return_value = {"result": []}
        mock_data_api_instance.get_data_file_descriptions_by_search.return_value = {"result": []}

        # Paramètres préparés
        morpho_info = {"Taille": "var_taille"}
        prov_dict = {"Prov_Test": "http://fake-uri.com/prov/1"}
        datafile_prov = {"dummy_data.xlsx": {"prov_morpho_parameters": "Prov_Test"}}
        sci_obj_uri = {"Plant_1": "http://fake-uri.com/so/1", "Plant_2": "http://fake-uri.com/so/2"}
        mock_avancement = MagicMock() # Faux talkie-walkie pour tester le callback

        # 2. Act
        result = create_data(
            "dummy_data.xlsx", "dummy_miappe.xlsx", "test_user", fake_client,
            morpho_info, prov_dict, datafile_prov, sci_obj_uri, avancement_upload=mock_avancement
        )

        # 3. Assert
        assert result is True
        # Vérifie qu'on a bien appelé l'API pour ajouter des données
        assert mock_data_api_instance.add_list_data.called is True
        
        # On vérifie qu'on a bien envoyé 2 paquets (les 2 lignes de notre faux DataFrame)
        args, kwargs = mock_data_api_instance.add_list_data.call_args
        assert len(kwargs['body']) == 2 
        
        # On vérifie que le callback d'UI a bien été appelé pour rassurer l'utilisateur
        assert mock_avancement.called is True
        mock_avancement.assert_called_with("var_taille", 2)

    @patch('simple.data_import.connexion')
    @patch('simple.data_import.silex.DataApi')
    @patch('simple.data_import.silex.VariablesApi')
    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.os.path.basename')
    def test_create_data_skips_existing(self, mock_basename, mock_read_excel, MockExpApi, MockVarApi, MockDataApi, mock_connexion):
        """Teste que les données existantes sont ignorées (pas de doublons)"""
        # Même arrangement que précédemment...
        df_miappe = pd.DataFrame({"name": ["Exp_Test"]})
        fake_time = pd.Timestamp('2023-01-01 10:00:00')
        df_data = pd.DataFrame({
            "Plant ID": ["Plant_1"],
            "timestamp": [fake_time],
            "Angle": [45],
            "Round Order": [1],
            "Taille": [15.5]
        })
        mock_read_excel.side_effect = [df_miappe, df_data]
        mock_basename.return_value = "dummy_data.xlsx"

        # 2. On simule la donnée existante
        mock_existing_data = MagicMock()
        mock_existing_data.target = "http://fake-uri.com/so/1"
        
        # CORRECTION ICI : On doit impérativement localiser en UTC AVANT de convertir vers Helsinki
        mock_existing_data._date = fake_time.tz_localize('UTC').tz_convert('UTC').strftime("%Y-%m-%dT%H:%M:%S%z").replace('+', '.000+')
        
        mock_existing_data.metadata = {"Round Order": 1}
        
        mock_data_api_instance = MockDataApi.return_value
        mock_data_api_instance.search_data_list.return_value = {"result": [mock_existing_data]}
        mock_data_api_instance.get_data_file_descriptions_by_search.return_value = {"result": []}

        # Paramètres
        morpho_info = {"Taille": "var_taille"}
        sci_obj_uri = {"Plant_1": "http://fake-uri.com/so/1"}
        mock_avancement = MagicMock()

        # Act
        create_data(
            "dummy_data.xlsx", 
            "dummy_miappe.xlsx", 
            "test_user", 
            MagicMock(),
            morpho_info, 
            {"Prov_Test": "http://fake-uri.com/prov/1"}, # CORRECTION ICI
            {"dummy_data.xlsx": {"prov_morpho_parameters": "Prov_Test"}}, # ET ICI
            sci_obj_uri, 
            avancement_upload=mock_avancement
        )

        # Assert : Puisque la donnée existait, add_list_data ne doit pas être appelé !
        assert mock_data_api_instance.add_list_data.called is False
        
        # Le callback doit prévenir l'utilisateur que 0 donnée a été importée
        mock_avancement.assert_called_with("var_taille", 0)

    # ==========================================
    # TESTS POUR CREATE_SCI_OBJ
    # ==========================================

    @patch('simple.data_import.pd.DataFrame.to_excel') 
    @patch('simple.data_import.get_name_space')
    @patch('simple.data_import.pd.ExcelWriter')
    @patch('simple.data_import.os.makedirs')
    @patch('simple.data_import.silex.GermplasmApi')
    @patch('simple.data_import.silex.ScientificObjectsApi')
    @patch('simple.data_import.silex.OntologyApi')
    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.pd.read_excel')
    def test_create_sci_obj_success(self, mock_read_excel, MockExpApi, MockOntologyApi, MockSciObjApi, MockGermplasmApi, mock_makedirs, mock_excel_writer, mock_get_name_space, mock_to_excel):
        """Teste la création réussie de nouveaux objets scientifiques"""
        # 1. Arrange
        df_miappe = pd.DataFrame({
            "name": ["Exp_Test"],
            "start_date": ["2023-01-01"],
            "end_date": ["2023-12-31"],
            "scientific_object_type": ["vocabulary:Plant"]
        })
        
        df_data = pd.DataFrame({
            "Plant ID": ["Plant_1", "Plant_2"],
            "Germplasm": ["Apache", "Zea mays"],
            "Factor1": ['High', 'Low']
        })
        
        df_factors = pd.DataFrame({
            "name": ["Factor1"], 
            "description": ["Desc 1"]
        })



        df_precedent = pd.DataFrame(columns=["studyId", "obsUnitType"])
        
        mock_read_excel.side_effect = [df_miappe, df_factors, df_data, df_precedent]
        mock_get_name_space.return_value = ("fake_namespace:", "http://fake-base.com/")

        # Mocks API
        fake_client = MagicMock()
        
        mock_exp = MagicMock()
        mock_exp.uri = "http://fake-uri.com/exp/1"
        MockExpApi.return_value.search_experiments.return_value = {"result": [mock_exp]}
        
        mock_factor_level_1 = MagicMock()
        mock_factor_level_1.name = "High"
        mock_factor_level_1.uri = "http://fake-uri.com/factor/level/high"
        
        mock_factor_level_2 = MagicMock()
        mock_factor_level_2.name = "Low"
        mock_factor_level_2.uri = "http://fake-uri.com/factor/level/low"
        
        mock_factor_result = MagicMock()
        mock_factor_result.levels = [mock_factor_level_1, mock_factor_level_2]
        MockExpApi.return_value.get_available_factors.return_value = {"result": [mock_factor_result]}
        
        # Ontologie
        mock_ontology = MagicMock()
        mock_child = MagicMock()
        mock_child.uri = "http://fake-uri.com/ontology/plant"
        mock_ontology.children = [mock_child]
        MockOntologyApi.return_value.search_sub_classes_of.return_value = {"result": [mock_ontology]}
        
        # Objets scientifiques
        mock_sci_obj_api_instance = MockSciObjApi.return_value
        mock_sci_obj_api_instance.search_scientific_objects.return_value = {"result": []}
        mock_sci_obj_api_instance.create_scientific_object.return_value = {"result": ["http://fake-base.com/so/new"]}
        
        # Germplasmes
        mock_germ = MagicMock()
        mock_germ.uri = "http://fake-uri.com/germplasm/1"
        MockGermplasmApi.return_value.search_germplasm.return_value = {"result": [mock_germ]}

        # 2. Act
        sci_obj_uri, created_count = create_sci_obj("dummy_data.xlsx", "dummy_miappe.xlsx", fake_client)

        # 3. Assert
        assert created_count == 2
        assert "Plant_1" in sci_obj_uri
        assert "Plant_2" in sci_obj_uri
        assert mock_sci_obj_api_instance.create_scientific_object.call_count == 2

    @patch('simple.data_import.silex.ScientificObjectsApi')
    @patch('simple.data_import.silex.OntologyApi')
    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.pd.read_excel')
    @patch('simple.data_import.get_name_space')
    def test_create_sci_obj_skips_existing(self, mock_get_name_space, mock_read_excel, MockExpApi, MockOntologyApi, MockSciObjApi):
        """Teste que la fonction utilise le cache si l'objet existe déjà et ne le recrée pas"""
        # 1. Arrange
        df_miappe = pd.DataFrame({
            "name": ["Exp_Test"],
            "start_date": ["2023-01-01"],
            "end_date": ["2023-12-31"],
            "scientific_object_type": ["vocabulary:Plant"]
        })
        df_data = pd.DataFrame({
            "Plant ID": ["Plant_1"],
            "Germplasm": ["Apache"],
            "Factor1": [None]
        })
        df_factors = pd.DataFrame({
            "name": ["Factor1"], 
            "description": ["Desc 1"]
        })
        
        # Exactement 2 appels à read_excel nécessaires
        mock_read_excel.side_effect = [df_miappe,df_factors, df_data]
        mock_get_name_space.return_value = ("fake_namespace:", "http://fake-base.com/")
        
        fake_client = MagicMock()
        
        mock_exp = MagicMock()
        mock_exp.uri = "http://fake-uri.com/exp/1"
        MockExpApi.return_value.search_experiments.return_value = {"result": [mock_exp]}
        
        # CORRECTION ICI : Faux facteur
        mock_factor_level = MagicMock()
        mock_factor_level.name = "Fake_Level"
        mock_factor_level.uri = "http://fake-uri.com/factor/level/1"
        mock_factor_result = MagicMock()
        mock_factor_result.levels = [mock_factor_level]
        MockExpApi.return_value.get_available_factors.return_value = {"result": [mock_factor_result]}
        
        mock_ontology = MagicMock()
        mock_child = MagicMock()
        mock_child.uri = "http://fake-uri.com/ontology/plant"
        mock_ontology.children = [mock_child]
        MockOntologyApi.return_value.search_sub_classes_of.return_value = {"result": [mock_ontology]}
        
        # Cache
        mock_sci_obj_api_instance = MockSciObjApi.return_value
        mock_existing_obj = MagicMock()
        mock_existing_obj.name = "Plant_1"
        mock_existing_obj.uri = "http://fake-uri.com/so/existing"
        mock_sci_obj_api_instance.search_scientific_objects.return_value = {"result": [mock_existing_obj]}

        # 2. Act
        sci_obj_uri, created_count = create_sci_obj("dummy_data.xlsx", "dummy_miappe.xlsx", fake_client)

        # 3. Assert
        assert created_count == 0 
        assert "Plant_1" in sci_obj_uri
        assert sci_obj_uri["Plant_1"] == "http://fake-uri.com/so/existing"
        assert mock_sci_obj_api_instance.create_scientific_object.called is False

    @patch('simple.data_import.silex.ExperimentsApi')
    @patch('simple.data_import.pd.read_excel')
    def test_create_sci_obj_missing_experiment_raises_error(self, mock_read_excel, MockExpApi):
        """Teste qu'une erreur est levée si le nom de l'expérience n'existe pas"""
        df_miappe = pd.DataFrame({
            "name": ["Exp_Inconnue"],
            "scientific_object_type": ["vocabulary:Plant"]
        })
        df_data = pd.DataFrame({"Plant ID": ["Plant_1"]})
        df_factors = pd.DataFrame({
            "name": ["Factor1"], 
            "description": ["Desc 1"]
        })

        mock_read_excel.side_effect = [df_miappe,df_factors, df_data]
        
        fake_client = MagicMock()
        
        # On simule un résultat vide pour la recherche d'expérience
        MockExpApi.return_value.search_experiments.return_value = {} 
        
        with pytest.raises(DataImportError) as error_info:
            create_sci_obj("dummy_data.xlsx", "dummy_miappe.xlsx", fake_client)
            
        assert "Exp_Inconnue" in str(error_info.value)