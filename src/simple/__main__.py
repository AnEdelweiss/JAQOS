import argparse

from simple.cli import main as cli_main
from simple.gui import main as gui_main


def main():
    parser = argparse.ArgumentParser(description="SIMPLE - Scientific data import tool")
    parser.add_argument(
        "--gui", 
        action="store_true", 
        help="Launch the graphical user interface"
    )
    
    # Parse known args in case uv passes extra arguments
    args, unknown = parser.parse_known_args()

    if args.gui:
        gui_main()
    else:
        cli_main()

if __name__ == "__main__":
    main()