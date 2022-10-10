import sys
from anonymizedf.app import AnonymizerApp

if __name__ == "__main__":
    app = AnonymizerApp(sys.argv[1:])
    app.MainLoop()
