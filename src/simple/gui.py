import sys

import opensilexClientToolsPython as silex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from simple.auth import INSTANCES, check_connection_internet, connexion, is_connected
from simple.data_import import (
    create_data,
    create_factor,
    create_germplasm,
    create_sci_obj,
    data_mapping,
    get_provenances,
)
from simple.datafile_import import (
    check_for_datafiles,
    execute_datafiles_upload,
    get_round_protocol_info,
)
from simple.erreurs import (
    AuthenticationError,
    DataImportError,
    NetworkError,
    SimpleBaseException,
)
from simple.experiment import api_find_experiment_by_name, create_experiment
from simple.systeme_logs import logger


class SimpleGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIMPLE GUI")
        self.setMinimumSize(400, 300)

        # INITIALISATION DES VARIABLES et de l'api ~
        self.silex_API_Client = silex.ApiClient(verbose=False)
        self.login_info = None
        self.wd_experience = None
        self.document_miappe = None
        self.document_data = None
        self.repertoire_photos = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Not logged in.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.btn_login = QPushButton("1. Log In")
        self.btn_login.clicked.connect(self.action_login)
        layout.addWidget(self.btn_login)

        self.btn_find_exp = QPushButton("2. Find Experiment")
        self.btn_find_exp.clicked.connect(self.action_find_experiment)
        layout.addWidget(self.btn_find_exp)

        self.btn_import_menu = QPushButton("3. Import Data")
        self.btn_import_menu.clicked.connect(self.action_open_import_menu)
        layout.addWidget(self.btn_import_menu)

        self.btn_reset = QPushButton("4. Reset Working Directory")
        self.btn_reset.clicked.connect(self.action_reset)
        layout.addWidget(self.btn_reset)

        self.btn_quit = QPushButton("Quit")
        self.btn_quit.clicked.connect(self.close)
        layout.addWidget(self.btn_quit)

    def action_login(self):
        host_display, ok = QInputDialog.getItem(
            self, "Login", "Select host instance:", list(INSTANCES.values()), 0, False
        )
        if not ok:
            return
        
        host = next(key for key, value in INSTANCES.items() if value == host_display)
        identifier, ok = QInputDialog.getText(self, "Login", "Identifier:")
        if not ok:
            return
        password, ok = QInputDialog.getText(
            self, "Login", "Password:", QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        self.login_info = {"host": host, "identifier": identifier, "password": password}

        try:
            connexion(self.login_info, self.silex_API_Client)
            self.status_label.setText(f"Logged in as {identifier} on {INSTANCES[host]}")
            QMessageBox.information(self, "Success", "Connected successfully.")
        except AuthenticationError as e:
            QMessageBox.critical(self, "Auth Error", str(e))

    def action_find_experiment(self):
        if not is_connected(self.silex_API_Client):
            QMessageBox.warning(self, "Error", "Please log in first.")
            return

        name_exp, ok = QInputDialog.getText(self, "Find Experiment", "Experiment name:")
        if ok and name_exp:
            self.with_progress(
                "Searching...",
                lambda: api_find_experiment_by_name(self.silex_API_Client, name_exp),
                self._display_experiment,
            )

    def _display_experiment(self, exp_data):
        if not exp_data:
            QMessageBox.information(self, "Result", "No experiment found.")
            return
        exp = exp_data[0]
        details = f"URI: {exp.uri}\n\nName: {exp.name}\n\nDescription: {exp.description}\n\nObjectives: {exp.objective}"
        QMessageBox.information(self, "Experiment Info", details)

    def action_open_import_menu(self):
        if not is_connected(self.silex_API_Client):
            QMessageBox.warning(self, "Error", "Please log in first.")
            return

        if not self.wd_experience:
            self.wd_experience = QFileDialog.getExistingDirectory(
                self, "Select Working Directory"
            )
            if not self.wd_experience:
                return

            self.document_miappe, _ = QFileDialog.getOpenFileName(
                self,
                "Select MIAPPE file",
                self.wd_experience,
                "Excel Files (*.xlsx *.xls)",
            )
            self.document_data, _ = QFileDialog.getOpenFileName(
                self, "Select Data file", self.wd_experience, "Excel Files (*.xlsx xls)"
            )

        self.import_dialog = QDialog(self)
        self.import_dialog.setWindowTitle("Experiment Menu")
        layout = QVBoxLayout(self.import_dialog)

        buttons = [
            ("1. Create Experiment", self.do_create_experiment),
            ("2. Import Germplasm", self.do_import_germplasm),
            ("3. Import Factor", self.do_import_factor),
            ("4. Import Scientific Objects", self.do_import_sci_obj),
            ("5. Import Datafiles", self.do_import_datafiles),
            ("6. Import Tabular Data", self.do_import_data),
            ("7. Run All Imports", self.do_run_all),
        ]

        for text, func in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            layout.addWidget(btn)

        self.import_dialog.exec()

    def action_reset(self):
        self.wd_experience = None
        self.document_miappe = None
        self.document_data = None
        self.repertoire_photos = None
        QMessageBox.information(
            self, "Reset", "Working directory and selected files have been reset."
        )

    def with_progress(self, message, func, callback=None):
        self.progress = QProgressDialog(message, None, 0, 0, self)
        self.progress.setWindowTitle("Please wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents() 

        try:
            result = func()
            if callback:
                callback(result)
        except SimpleBaseException as e:
            logger.warning(f"Action interrupted : {e}")
            QMessageBox.warning(self, "Warning", str(e))
        except Exception as e:
            logger.exception(f"Error: {e}")
            QMessageBox.critical(self, "Error", f"An Unhandled Error was raised: {e}")
        finally:
            self.progress.close()
            QApplication.restoreOverrideCursor()

    def _status_callback(self, message):
        QApplication.processEvents()

    def do_create_experiment(self):
        def task():
            return create_experiment(
                self.document_miappe,
                self.silex_API_Client,
                status_callback=self._status_callback,
            )

        def finish(results):
            # affichage final
            msg = "\n".join([f"experiment created or found : {nom}: {uri}" for nom, uri in results.items()])
            QMessageBox.information(self, "Experiment creater or found", msg)

        self.with_progress("Processing experiment data...", task, finish)

    def do_import_germplasm(self):
        def task():
            return create_germplasm(self.document_miappe, self.silex_API_Client)

        self.with_progress(
            "Importing germplasms...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Germplasms imported."),
        )

    def do_import_factor(self):
        def task():
            return create_factor(self.document_miappe, self.silex_API_Client)

        self.with_progress(
            "Importing factors...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Factors imported."),
        )

    def do_import_sci_obj(self):
        def task():
            return create_sci_obj(
                self.document_data,
                self.document_miappe,
                self.silex_API_Client,
                status_callback=self._status_callback,
            )

        def finish(res):
            sci_obj_uri, created_sci_obj = res
            found = len(sci_obj_uri) - created_sci_obj
            QMessageBox.information(
                self, "Scientific Objects", f"{found} scientific objects found and {created_sci_obj} created."
            )

        self.with_progress("Importing scientific objects...", task, finish)

    def do_import_datafiles(self):
        # on choisit le dossier photo ici
        self.repertoire_photos = QFileDialog.getExistingDirectory(self, "Select Photo Directory", self.wd_experience)
        if not self.repertoire_photos: return

        def task():
            # taking care of provenances
            prov_dict, datafile_provenance, missing_provs = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client)
            if missing_provs:
                prov_dict, datafile_provenance, _ = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client, create_default=True)
            
            # getting scientific object uris etc...
            sci_obj_uri, _ = create_sci_obj(self.document_data, self.document_miappe, self.silex_API_Client)
            
            # getting cam_pos and plant_mask
            cam_pos, plant_mask, protocol_found = get_round_protocol_info(self.wd_experience, self.document_data)
            if not protocol_found:
                 logger.warning("PlantMask and Camera Position were not found")
            
            # on compare les datafiles et ceux données dans les données tabulaires
            dict_datafile1, missing_datafile1, dict_datafile2, missing_datafile2, has_datafile2, df_data = check_for_datafiles(self.document_data, self.repertoire_photos)
            
            if missing_datafile1 or missing_datafile2:
                logger.warning(f"{missing_datafile1} & {missing_datafile2}")
                reply = QMessageBox.question(
                    self, 
                    "Discrepancies found", 
                    "Datafiles are missing. Continue despite discrepancies? The import may fail.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    raise SimpleBaseException("User cancelled action after database discrepancies were found.")

            self.current_progress = 0

            def gui_progress(nom_tache, total=None, avance=0):
                if total:
                    self.progress.setMaximum(total)
                
                self.current_progress += avance
                self.progress.setValue(self.current_progress)
                self.progress.setLabelText(f"{nom_tache}...")
                QApplication.processEvents()

            # enfin on téléverse :
            execute_datafiles_upload(
                self.document_miappe, self.document_data, df_data, dict_datafile1, dict_datafile2, 
                has_datafile2, prov_dict, datafile_provenance, sci_obj_uri, cam_pos, plant_mask, 
                self.login_info, self.silex_API_Client, status_callback=self._status_callback, progress_callback=gui_progress
            )

        self.with_progress("Importing datafiles...", task, lambda r: QMessageBox.information(self, "Success", "Datafiles imported or found sucessfully."))

    def do_import_data(self):
        def task():
            # on apelle data_mapping pour faire le lien noms colonnes données tabulaires -> variables phis
            morpho_info = data_mapping(self.document_data, self.document_miappe)

            # on s'occupe des provenances et du retour console s'il en manque etc...
            prov_dict, datafile_provenance, missing_provs = get_provenances(
                self.document_data, self.document_miappe, self.silex_API_Client
            )
            if missing_provs:
                prov_dict, datafile_provenance, _ = get_provenances(
                    self.document_data,
                    self.document_miappe,
                    self.silex_API_Client,
                    create_default=True,
                )

            # on récupère le dictionnaire d'objets scientifiques
            sci_obj_uri, _ = create_sci_obj(
                self.document_data, self.document_miappe, self.silex_API_Client
            )

            # on gère l'affichage des progression d'importation de données
            def afficher_progres(nom_variable, nb_lignes):
                self._status_callback(f"Added {nb_lignes} to {nom_variable}")

            create_data(
                self.document_data,
                self.document_miappe,
                self.login_info,
                self.silex_API_Client,
                morpho_info,
                prov_dict,
                datafile_provenance,
                sci_obj_uri,
                avancement_upload=afficher_progres,
            )

        self.with_progress(
            "Importing tabular data...",
            task,
            lambda r: QMessageBox.information(
                self, "Success", "Data imported or found successfully."
            ),
        )

    def do_run_all(self):
        self.do_create_experiment()
        self.do_import_germplasm()
        self.do_import_factor()
        self.do_import_sci_obj()
        self.do_import_datafiles()
        self.do_import_data()


def main():
    try:
        check_connection_internet()
    except NetworkError as e:
        logger.error(f"Network Error: {e}")
        return

    app = QApplication(sys.argv)
    window = SimpleGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
