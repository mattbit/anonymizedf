import sys
from anonymizedf import App

if __name__ == "__main__":
    app = App(sys.argv[1:])
    app.MainLoop()
