import logging
import sys
import pandas as pd
import opensilexClientToolsPython as silex
from PyQt6.QtCore import QObject, Qt, pyqtSignal,QThread
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
    NetworkError,
    SimpleBaseException,
)
from simple.experiment import api_find_experiment_by_name, create_experiment
from simple.systeme_logs import logger


# 1. The Signal Emitter (Safely crosses threads)
class LogEmitter(QObject):
    log_signal = pyqtSignal(str)

class WorkerThread(QThread):
    # These signals safely carry our results back to the main GUI thread
    finished_success = pyqtSignal(object) 
    finished_error = pyqtSignal(Exception)

    def __init__(self, task_func):
        super().__init__()
        self.task_func = task_func

    def run(self):
        try:
            # Execute the heavy backend function
            result = self.task_func()
            self.finished_success.emit(result)
        except Exception as e:
            # If anything crashes in the backend, catch it and tell the GUI
            self.finished_error.emit(e)

# 2. The Custom Logging Handler
class GUIConsoleHandler(logging.Handler):
    def __init__(self, emitter):
        super().__init__()
        self.emitter = emitter
        self.setLevel(logging.INFO)

    def emit(self, record):
        msg = self.format(record)
        
        # Map log levels to specific colors
        if record.levelno == logging.WARNING:
            color = "#FFA500" # Orange
        elif record.levelno >= logging.ERROR:
            color = "#FF4C4C" # Red
        else:
            color = "#008000" # Light green (Standard INFO)

        # Wrap the message in an HTML span tag
        html_msg = f'<span style="color: {color};">{msg}</span>'
        self.emitter.log_signal.emit(html_msg)

class SimpleGUI(QMainWindow):

    gui_progress_signal = pyqtSignal(str, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIMPLE GUI")
        self.setMinimumSize(500, 500)

        # INITIALISATION DES VARIABLES et de l'api ~
        self.silex_API_Client = silex.ApiClient(verbose=False)
        self.login_info = None
        self.wd_experience = None
        self.document_miappe = None
        self.document_data = None
        self.repertoire_photos = None

        self.init_ui()
        self.gui_progress_signal.connect(self._safe_update_progress)
        self.current_progress = 0

    def _safe_update_progress(self, label_text, advance=0, total=0):
        """This function always runs on the main thread and safely updates the UI."""
        if not hasattr(self, 'progress') or self.progress.wasCanceled():
            return

        # Only reset the progress and update the maximum if a NEW total is provided.
        # This prevents the bar from resetting to 0 if the backend repeatedly sends the same total.
        if total > 0 and self.progress.maximum() != total:
            self.progress.setMaximum(total)
            self.current_progress = 0 # Reset only when the total changes
            
        self.current_progress += advance
        self.progress.setValue(self.current_progress)
        self.progress.setLabelText(f"{label_text}...")

    def closeEvent(self, event):
        # Clean up the logger handler when the app closes
        logger.removeHandler(self.gui_logger_handler)
        super().closeEvent(event)
        

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

        # --- NEW CONSOLE WIDGET ---
        layout.addWidget(QLabel("Console Output:"))
        from PyQt6.QtWidgets import QPlainTextEdit
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        # Optional: set a darker background to make it look like a terminal
        self.console_output.setStyleSheet(
            "background-color: #1e1e1e; "
            "color: #d4d4d4; "
            "font-family: monospace; "
            "font-size: 14px; "
            "font-weight: bold;"
        )
        layout.addWidget(self.console_output)

        # --- WIRE THE LOGGER TO THE CONSOLE ---
        self.log_emitter = LogEmitter()
        self.log_emitter.log_signal.connect(self.console_output.appendHtml)

        self.gui_logger_handler = GUIConsoleHandler(self.log_emitter)
        self.gui_logger_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
        # Attach our custom handler to the engine's logger
        logger.addHandler(self.gui_logger_handler)


    def action_login(self):
        host_display, ok = QInputDialog.getItem(
            self, "Login", "Select host instance:", list(INSTANCES.values()), 0, False
        )
        if not ok:
            return
        
        host = next(key for key, value in INSTANCES.items() if value == host_display)
        if host == "https://opensilex.org/sandbox/rest":
            identifier="guest@opensilex.org"
            password="guest"
            self.login_info = {"host": host, "identifier": identifier, "password": password}
        else:
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
    
    def with_progress(self, message, task_func, on_success_callback=None, indeterminate=False):
        # 1. Setup the beautiful, non-freezing Progress Dialog
        self.progress = QProgressDialog(message, None, 0, 100, self) 
        self.progress.setWindowTitle("Please wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setAutoClose(False) 
        
        # Explicitly reset the internal progress tracker for each new task
        self.current_progress = 0 
        
        if indeterminate:
            # Setting max and min to 0 triggers the infinite loading animation
            self.progress.setMaximum(0)
            self.progress.setMinimum(0)
        else:
            self.progress.setValue(0)
            
        self.progress.show()

        # 2. Create the background worker
        self.worker = WorkerThread(task_func)

        # 3. Connect the success signal
        if on_success_callback:
            # When the worker finishes successfully, close the bar and run the callback
            self.worker.finished_success.connect(self.progress.close)
            self.worker.finished_success.connect(on_success_callback)

        # 4. Connect the error signal (Crucial: prevents silent crashes!)
        def handle_error(e):
            self.progress.close()
            logger.error(f"Task Failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred during import:\n{str(e)}")
            
        self.worker.finished_error.connect(handle_error)

        # 5. Start the thread! The GUI remains 100% responsive.
        self.worker.start()

    def _status_callback(self, message):
        logger.info(message)

    def do_create_experiment(self):
        def task():
            return create_experiment(
                self.document_miappe,
                self.silex_API_Client,
                status_callback=self._status_callback,
            )

        def finish(results):
            # affichage final
            msg = "\n".join([f"experiment {nom} created or found with uri: {uri}" for nom, uri in results.items()])
            QMessageBox.information(self, "Experiment creater or found", msg)

        self.with_progress(
            "Creating/fetching experiment...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Experiment imported/found."),
            indeterminate=True
        )

    def do_import_germplasm(self):
        def task():
            return create_germplasm(self.document_miappe, self.silex_API_Client)

        self.with_progress(
            "Creating/fetching germplasms...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Germplasms imported/found."),
            indeterminate=True
        )

    def do_import_factor(self):
        def task():
            return create_factor(self.document_miappe, self.silex_API_Client)

        self.with_progress(
            "Creating/fetching factors...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Factors imported/found."),
            indeterminate=True 
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
        self.with_progress(
            "Creating/fetching factors...",
            task,
            finish,
            indeterminate=True,
        )

    def do_import_datafiles(self):
        self.repertoire_photos = QFileDialog.getExistingDirectory(self, "Select Photo Directory", self.wd_experience)
        if not self.repertoire_photos: return

        # 1. UI interaction must happen in the main thread before starting the background task
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
                return

        def task():
            prov_dict, datafile_provenance, missing_provs = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client)
            if missing_provs:
                prov_dict, datafile_provenance, _ = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client, create_default=True)
            
            sci_obj_uri, _ = create_sci_obj(self.document_data, self.document_miappe, self.silex_API_Client)
            
            cam_pos, plant_mask, protocol_found = get_round_protocol_info(self.wd_experience, self.document_data)
            if not protocol_found:
                 logger.warning("PlantMask and Camera Position were not found")

            # 2. Use the thread-safe signals for progress
            def afficher_statut(mess):
                logger.info(mess)

            def gestion_barre(nom_tache, total=None, avance=0):
                safe_total = total if total is not None else 0
                self.gui_progress_signal.emit(nom_tache, avance, safe_total)

            execute_datafiles_upload(
                self.document_miappe, self.document_data, df_data, dict_datafile1, dict_datafile2, 
                has_datafile2, prov_dict, datafile_provenance, sci_obj_uri, cam_pos, plant_mask, 
                self.login_info, self.silex_API_Client, status_callback=afficher_statut, progress_callback=gestion_barre
            )

        # 3. Use a lambda for the missing success_callback
        self.with_progress(
            "Importing datafiles...", 
            task, 
            lambda r: QMessageBox.information(self, "Success", "Datafiles imported successfully.")
        )

    def do_import_data(self):
        def task():
            morpho_info = data_mapping(self.document_data, self.document_miappe)

            prov_dict, datafile_provenance, missing_provs = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client)
            if missing_provs:
                prov_dict, datafile_provenance, _ = get_provenances(self.document_data, self.document_miappe, self.silex_API_Client, create_default=True)

            sci_obj_uri, _ = create_sci_obj(self.document_data, self.document_miappe, self.silex_API_Client)
            # Calculate the total upfront (number of variables * number of rows)
            df_length = len(pd.read_excel(self.document_data))
            total_operations = len(morpho_info) * df_length

            def afficher_progres(nom_variable, nb_lignes):
                # Pass the calculated total so the UI knows how to scale
                self.gui_progress_signal.emit(f"Adding to {nom_variable}", nb_lignes, total_operations)

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
        
        # 3. Use a lambda for the missing success_callback
        self.with_progress(
            "Importing tabular data...", 
            task, 
            lambda r: QMessageBox.information(self, "Success", "Tabular data imported successfully.")
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
