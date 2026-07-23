import pytest
import requests
from unittest.mock import patch, MagicMock

# Assure-toi d'adapter les imports à l'arborescence exacte de ton projet
from simple.erreurs import NetworkError, AuthenticationError
from simple.auth import (
    check_connection_internet,
    is_connected,
    deconnexion,
    connexion,
    get_login
)

class TestAuth:
    
    # ==========================================
    # TESTS POUR CHECK_CONNECTION_INTERNET
    # ==========================================

    @patch('simple.auth.requests.get')
    def test_check_connection_internet_success(self, mock_get):
        """Teste que la fonction passe silencieusement si internet fonctionne"""
        # Le mock ne lève aucune exception (simule un code 200 OK)
        check_connection_internet()
        # On vérifie que la requête a bien été tentée
        assert mock_get.called is True

    @patch('simple.auth.requests.get')
    def test_check_connection_internet_failure(self, mock_get):
        """Teste qu'une erreur réseau lève bien la NetworkError personnalisée"""
        # On simule un timeout ou une coupure réseau
        mock_get.side_effect = requests.ConnectionError("Pas de connexion")
        
        with pytest.raises(NetworkError) as error_info:
            check_connection_internet()
            
        assert "No internet acess :/" in str(error_info.value)

    # ==========================================
    # TESTS POUR IS_CONNECTED
    # ==========================================

    def test_is_connected_true(self):
        """Teste que la fonction repère bien l'en-tête d'autorisation"""
        mock_client = MagicMock()
        mock_client.default_headers = {'Authorization': 'Bearer token123'}
        
        assert is_connected(mock_client) is True

    def test_is_connected_false(self):
        """Teste le renvoi False quand il n'y a pas d'autorisation"""
        mock_client = MagicMock()
        mock_client.default_headers = {} # Pas d'autorisation
        
        assert is_connected(mock_client) is False

    # ==========================================
    # TESTS POUR DECONNEXION
    # ==========================================

    @patch('simple.auth.silex.AuthenticationApi')
    def test_deconnexion_success(self, MockAuthApi):
        """Teste la déconnexion et la suppression du token"""
        mock_client = MagicMock()
        mock_client.default_headers = {'Authorization': 'Bearer token123'}
        
        result = deconnexion(mock_client)
        
        assert result is True
        # L'en-tête doit avoir été supprimé
        assert 'Authorization' not in mock_client.default_headers

    @patch('simple.auth.silex.AuthenticationApi')
    def test_deconnexion_failure(self, MockAuthApi):
        """Teste que la fonction attrape l'erreur sans crasher si la déco échoue"""
        mock_client = MagicMock()
        mock_client.default_headers = {'Authorization': 'Bearer token123'}
        
        # On simule une erreur lors de l'appel à l'API
        MockAuthApi.side_effect = Exception("Erreur serveur inattendue")
        
        result = deconnexion(mock_client)
        
        assert result is False
        # Comme ça a planté, l'en-tête n'a pas pu être supprimé
        assert 'Authorization' in mock_client.default_headers

    # ==========================================
    # TESTS POUR CONNEXION
    # ==========================================

    @patch('simple.auth.deconnexion')
    def test_connexion_success(self, mock_deconnexion):
        """Teste que la connexion appelle bien le SDK avec les bons paramètres"""
        mock_client = MagicMock()
        login_dict = {"host": "https://fake.url", "identifier": "user", "password": "pwd"}
        
        result = connexion(login_dict, mock_client)
        
        assert result is True
        # Vérifie qu'on a bien déconnecté d'abord
        mock_deconnexion.assert_called_once_with(mock_client)
        # Vérifie qu'on passe bien le dictionnaire déballé (**)
        mock_client.connect_to_opensilex_ws.assert_called_once_with(**login_dict)

    @patch('simple.auth.deconnexion')
    def test_connexion_api_error_json(self, mock_deconnexion):
        """Teste l'extraction du message d'erreur JSON renvoyé par OpenSilex"""
        mock_client = MagicMock()
        login_dict = {"host": "https://fake.url"}
        
        # On reproduit la chaîne exacte (assez laide) que l'API renvoie quand on se trompe de mdp
        faux_message_erreur = 'HTTP response body: {"result": {"message": "Invalid credentials provided"}}'
        mock_client.connect_to_opensilex_ws.side_effect = Exception(faux_message_erreur)
        
        with pytest.raises(AuthenticationError) as error_info:
            connexion(login_dict, mock_client)
            
        # On vérifie que notre fonction a bien décortiqué le JSON pour extraire le vrai message
        assert "Invalid credentials provided" in str(error_info.value)

    # ==========================================
    # TESTS POUR GET_LOGIN (INTERFACE)
    # ==========================================

    @patch('simple.auth.Prompt.ask')
    @patch('simple.auth.IntPrompt.ask')
    def test_get_login(self, mock_int_ask, mock_ask):
        """Teste la collecte des informations de connexion via Rich"""
        # On simule l'utilisateur qui tape '0' (Sandbox)
        mock_int_ask.return_value = 0
        
        # side_effect permet de donner les réponses successives : d'abord le nom, puis le mot de passe
        mock_ask.side_effect = ["mon_adresse@mail.com", "mon_mot_de_passe_secret"]
        
        login_dict = get_login()
        
        assert login_dict["host"] == "https://opensilex.org/sandbox/rest"
        assert login_dict["identifier"] == "mon_adresse@mail.com"
        assert login_dict["password"] == "mon_mot_de_passe_secret"