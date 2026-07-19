

class SimpleBaseException(Exception):
    """Classe de base pour toutes les exceptions de l'application SIMPLE."""
    pass

class NetworkError(SimpleBaseException):
    """Levée quand la connexion internet ou l'API échoue."""
    pass

class AuthenticationError(SimpleBaseException):
    """Levée pour les problèmes de login, de mots de passe ou de tokens."""
    pass

class DataImportError(SimpleBaseException):
    """Levée quand les données du fichier MIAPPE ou tabulaire sont manquantes ou invalides."""
    pass

class ConfigurationError(SimpleBaseException):
    """Levée quand un fichier ou un dossier attendu est introuvable sur la machine."""
    pass